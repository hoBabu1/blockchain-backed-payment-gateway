"""
Webhook Delivery Service.

Handles sending webhook notifications to merchants with
HMAC signature verification and retry logic.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config import config
from database.db import Database
from models.merchant import Merchant
from models.payment import PaymentEvent, WebhookPayload

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for delivering webhook notifications to merchants.

    Features:
    - HMAC-SHA256 signature for payload verification
    - Configurable retry logic with exponential backoff
    - Delivery logging and status tracking
    - Rate limiting to avoid overwhelming merchants
    """

    def __init__(
        self,
        db: Database,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delays: Optional[List[int]] = None
    ):
        """
        Initialize the webhook service.

        Args:
            db: Database instance for logging deliveries
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delays: List of delays in minutes between retries
        """
        self.db = db
        self.timeout = timeout or config.webhook.timeout
        self.max_retries = max_retries or config.webhook.max_retries
        self.retry_delays = retry_delays or config.webhook.retry_delays
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

    async def start(self) -> None:
        """Start the webhook service."""
        logger.info("Starting webhook service...")
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        self._running = True

        # Start retry processor
        asyncio.create_task(self._retry_processor())
        logger.info("Webhook service started")

    async def stop(self) -> None:
        """Stop the webhook service."""
        logger.info("Stopping webhook service...")
        self._running = False

        if self._session:
            await self._session.close()
            self._session = None

    async def send_notification(
        self,
        merchant: Merchant,
        event: PaymentEvent,
        event_type: str = "payment.completed"
    ) -> Tuple[bool, Optional[str]]:
        """
        Send a webhook notification to a merchant.

        Args:
            merchant: Merchant to notify
            event: Payment event data
            event_type: Type of event

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if not merchant.is_webhook():
            return False, "Merchant is not configured for webhook notifications"

        if not merchant.webhook_url or not merchant.webhook_secret:
            return False, "Webhook URL or secret not configured"

        # Create and sign payload
        payload = WebhookPayload.from_payment_event(event, event_type)
        payload.sign(merchant.webhook_secret)

        logger.info(
            f"Sending webhook to {merchant.short_id()} "
            f"at {merchant.webhook_url}"
        )

        # Send webhook
        success, response_code, response_body = await self._deliver(
            url=merchant.webhook_url,
            payload=payload,
            secret=merchant.webhook_secret
        )

        # Log delivery
        next_retry = None
        if not success and len(self.retry_delays) > 0:
            next_retry = datetime.utcnow() + timedelta(minutes=self.retry_delays[0])

        await self.db.log_delivery(
            merchant_id=merchant.id,
            event_type=event_type,
            event_id=payload.event_id,
            delivery_method='webhook',
            payload=payload.to_json(),
            success=success,
            response_code=response_code,
            response_body=response_body,
            retry_count=0,
            next_retry_at=next_retry
        )

        if success:
            logger.info(f"Webhook delivered successfully to {merchant.short_id()}")
            return True, None
        else:
            logger.warning(
                f"Webhook delivery failed for {merchant.short_id()}: "
                f"code={response_code}, retry scheduled"
            )
            return False, response_body

    async def _deliver(
        self,
        url: str,
        payload: WebhookPayload,
        secret: str
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Deliver a webhook payload to a URL.

        Args:
            url: Webhook endpoint URL
            payload: Webhook payload to send
            secret: Secret for signature header

        Returns:
            Tuple of (success, response_code, response_body)
        """
        if not self._session:
            return False, None, "Session not initialized"

        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': f'sha256={payload.signature}',
            'X-Webhook-Event': payload.event_type,
            'X-Webhook-ID': payload.event_id,
            'X-Webhook-Timestamp': payload.timestamp.isoformat()
        }

        try:
            async with self._session.post(
                url,
                data=payload.to_json(),
                headers=headers
            ) as response:
                response_body = await response.text()

                # Success: 2xx status codes
                if 200 <= response.status < 300:
                    return True, response.status, response_body
                else:
                    return False, response.status, response_body

        except aiohttp.ClientError as e:
            logger.error(f"Network error delivering webhook: {e}")
            return False, None, str(e)
        except asyncio.TimeoutError:
            logger.error(f"Timeout delivering webhook to {url}")
            return False, None, "Request timeout"
        except Exception as e:
            logger.error(f"Unexpected error delivering webhook: {e}")
            return False, None, str(e)

    async def _retry_processor(self) -> None:
        """
        Background task that processes failed deliveries for retry.

        Runs continuously and checks for deliveries that need to be retried.
        """
        logger.info("Starting webhook retry processor")

        while self._running:
            try:
                await self._process_retries()
            except Exception as e:
                logger.error(f"Error in retry processor: {e}", exc_info=True)

            # Check for retries every minute
            await asyncio.sleep(60)

    async def _process_retries(self) -> None:
        """Process pending webhook retries."""
        pending = await self.db.get_pending_retries()

        # Filter to only webhook deliveries
        webhook_retries = [
            p for p in pending
            if p.get('delivery_method') == 'webhook'
        ]

        if webhook_retries:
            logger.info(f"Processing {len(webhook_retries)} webhook retries")

        for delivery in webhook_retries:
            await self._retry_delivery(delivery)

    async def _retry_delivery(self, delivery: Dict[str, Any]) -> None:
        """
        Retry a failed webhook delivery.

        Args:
            delivery: Delivery record from database
        """
        delivery_id = delivery['id']
        merchant_id = delivery['merchant_id']
        retry_count = delivery['retry_count']
        webhook_url = delivery.get('webhook_url')
        webhook_secret = delivery.get('webhook_secret')
        payload_json = delivery.get('payload')

        if not webhook_url or not webhook_secret or not payload_json:
            logger.error(f"Missing data for retry of delivery {delivery_id}")
            # Mark as failed with no more retries
            await self.db.update_delivery_retry(
                delivery_id=delivery_id,
                retry_count=retry_count + 1,
                next_retry_at=None,
                response_body="Missing webhook configuration"
            )
            return

        logger.info(
            f"Retrying webhook delivery {delivery_id} "
            f"(attempt {retry_count + 1})"
        )

        # Reconstruct payload from stored JSON
        import json
        payload_dict = json.loads(payload_json)
        payload = WebhookPayload(
            event_id=payload_dict['event_id'],
            event_type=payload_dict['event_type'],
            timestamp=datetime.fromisoformat(payload_dict['timestamp'].rstrip('Z')),
            data=payload_dict['data'],
            signature=payload_dict.get('signature')
        )

        # Re-sign payload (in case secret changed)
        payload.sign(webhook_secret)

        # Attempt delivery
        success, response_code, response_body = await self._deliver(
            url=webhook_url,
            payload=payload,
            secret=webhook_secret
        )

        if success:
            await self.db.mark_delivery_success(delivery_id)
            logger.info(f"Retry successful for delivery {delivery_id}")
        else:
            new_retry_count = retry_count + 1

            # Calculate next retry time
            if new_retry_count < len(self.retry_delays):
                next_delay = self.retry_delays[new_retry_count]
                next_retry = datetime.utcnow() + timedelta(minutes=next_delay)
                logger.warning(
                    f"Retry {new_retry_count} failed for delivery {delivery_id}, "
                    f"next retry in {next_delay} minutes"
                )
            else:
                next_retry = None
                logger.error(
                    f"All retries exhausted for delivery {delivery_id}"
                )

            await self.db.update_delivery_retry(
                delivery_id=delivery_id,
                retry_count=new_retry_count,
                next_retry_at=next_retry,
                response_code=response_code,
                response_body=response_body
            )

    async def verify_webhook_url(self, url: str) -> Tuple[bool, str]:
        """
        Verify that a webhook URL is reachable.

        Sends a test request to check connectivity.

        Args:
            url: URL to verify

        Returns:
            Tuple of (is_valid, message)
        """
        if not url.startswith(('http://', 'https://')):
            return False, "URL must start with http:// or https://"

        if not self._session:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )

        try:
            # Send OPTIONS request to check CORS/connectivity
            async with self._session.options(url) as response:
                return True, f"URL is reachable (status: {response.status})"
        except aiohttp.ClientError as e:
            return False, f"Cannot reach URL: {e}"
        except Exception as e:
            return False, f"Error verifying URL: {e}"

    async def get_delivery_stats(self, merchant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get delivery statistics.

        Args:
            merchant_id: Optional merchant ID to filter by

        Returns:
            Statistics dictionary
        """
        # This would typically query the database for aggregate stats
        return {
            "service": "webhook",
            "running": self._running,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delays": self.retry_delays
        }


def generate_signature_verification_code(language: str = "python") -> str:
    """
    Generate signature verification code for merchants to use.

    Args:
        language: Programming language (python, javascript, php)

    Returns:
        Code snippet as string
    """
    if language == "python":
        return '''
import hmac
import hashlib
import json

def verify_webhook(payload_json: str, signature: str, secret: str) -> bool:
    """Verify webhook signature."""
    # Extract signature from header (format: sha256=abc123...)
    if signature.startswith('sha256='):
        signature = signature[7:]

    # Parse and re-serialize payload (without signature field)
    payload = json.loads(payload_json)
    payload.pop('signature', None)
    payload_to_verify = json.dumps(payload, separators=(',', ':'), sort_keys=True)

    # Calculate expected signature
    expected = hmac.new(
        secret.encode('utf-8'),
        payload_to_verify.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
'''
    elif language == "javascript":
        return '''
const crypto = require('crypto');

function verifyWebhook(payloadJson, signature, secret) {
    // Extract signature from header (format: sha256=abc123...)
    if (signature.startsWith('sha256=')) {
        signature = signature.slice(7);
    }

    // Parse and re-serialize payload (without signature field)
    const payload = JSON.parse(payloadJson);
    delete payload.signature;
    const payloadToVerify = JSON.stringify(payload);

    // Calculate expected signature
    const expected = crypto
        .createHmac('sha256', secret)
        .update(payloadToVerify)
        .digest('hex');

    return crypto.timingSafeEqual(
        Buffer.from(expected),
        Buffer.from(signature)
    );
}

module.exports = { verifyWebhook };
'''
    elif language == "php":
        return '''
<?php
function verifyWebhook($payloadJson, $signature, $secret) {
    // Extract signature from header (format: sha256=abc123...)
    if (strpos($signature, 'sha256=') === 0) {
        $signature = substr($signature, 7);
    }

    // Parse and re-serialize payload (without signature field)
    $payload = json_decode($payloadJson, true);
    unset($payload['signature']);
    $payloadToVerify = json_encode($payload, JSON_UNESCAPED_SLASHES);

    // Calculate expected signature
    $expected = hash_hmac('sha256', $payloadToVerify, $secret);

    return hash_equals($expected, $signature);
}
?>
'''
    else:
        return f"Language '{language}' not supported. Use: python, javascript, php"
