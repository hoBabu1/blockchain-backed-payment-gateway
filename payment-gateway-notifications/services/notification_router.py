"""
Notification Router Service.

Routes payment notifications to the appropriate delivery service
based on merchant preferences (webhook or Telegram).
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from database.db import Database
from models.merchant import Merchant, NotificationType
from models.payment import PaymentEvent
from .webhook_service import WebhookService
from .telegram_service import TelegramService

logger = logging.getLogger(__name__)


class NotificationRouter:
    """
    Central router for payment notifications.

    Determines the appropriate notification service for each merchant
    and handles delivery with proper error handling and logging.
    """

    def __init__(
        self,
        db: Database,
        webhook_service: WebhookService,
        telegram_service: TelegramService
    ):
        """
        Initialize the notification router.

        Args:
            db: Database instance
            webhook_service: Webhook delivery service
            telegram_service: Telegram delivery service
        """
        self.db = db
        self.webhook_service = webhook_service
        self.telegram_service = telegram_service
        self._running = False
        self._stats = {
            "total_notifications": 0,
            "webhook_sent": 0,
            "telegram_sent": 0,
            "webhook_failed": 0,
            "telegram_failed": 0,
            "merchant_not_found": 0,
            "already_processed": 0
        }

    async def start(self) -> None:
        """Start the notification router."""
        logger.info("Starting notification router...")
        self._running = True
        logger.info("Notification router started")

    async def stop(self) -> None:
        """Stop the notification router."""
        logger.info("Stopping notification router...")
        self._running = False

    async def route_notification(
        self,
        event: PaymentEvent,
        event_type: str = "payment.completed"
    ) -> Tuple[bool, Optional[str]]:
        """
        Route a payment notification to the appropriate service.

        Args:
            event: Payment event to notify about
            event_type: Type of event

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        self._stats["total_notifications"] += 1
        merchant_id = event.merchant_id

        logger.info(
            f"Routing notification for payment {event.short_payment_id()} "
            f"to merchant {event.short_merchant_address()}"
        )

        # Check if already processed (deduplication)
        already_processed = await self.db.check_event_processed(
            event_id=event.get_event_id(),
            merchant_id=merchant_id
        )
        if already_processed:
            self._stats["already_processed"] += 1
            logger.debug(f"Event {event.get_event_id()} already processed, skipping")
            return True, None

        # Look up merchant
        merchant_data = await self.db.get_merchant(merchant_id)

        if not merchant_data:
            self._stats["merchant_not_found"] += 1
            logger.warning(
                f"Merchant {event.short_merchant_address()} not registered, "
                f"cannot send notification"
            )
            return False, f"Merchant {merchant_id} not registered"

        merchant = Merchant.from_dict(merchant_data)

        # Check if merchant is active
        if not merchant.is_active:
            logger.info(f"Merchant {merchant.short_id()} is inactive, skipping notification")
            return False, "Merchant is inactive"

        # Route to appropriate service
        if merchant.notification_type == NotificationType.WEBHOOK:
            return await self._send_webhook(merchant, event, event_type)
        elif merchant.notification_type == NotificationType.TELEGRAM:
            return await self._send_telegram(merchant, event, event_type)
        else:
            logger.error(f"Unknown notification type: {merchant.notification_type}")
            return False, f"Unknown notification type: {merchant.notification_type}"

    async def _send_webhook(
        self,
        merchant: Merchant,
        event: PaymentEvent,
        event_type: str
    ) -> Tuple[bool, Optional[str]]:
        """Send notification via webhook."""
        success, error = await self.webhook_service.send_notification(
            merchant=merchant,
            event=event,
            event_type=event_type
        )

        if success:
            self._stats["webhook_sent"] += 1
            logger.info(f"Webhook notification sent to {merchant.short_id()}")
        else:
            self._stats["webhook_failed"] += 1
            logger.warning(f"Webhook notification failed for {merchant.short_id()}: {error}")

        return success, error

    async def _send_telegram(
        self,
        merchant: Merchant,
        event: PaymentEvent,
        event_type: str
    ) -> Tuple[bool, Optional[str]]:
        """Send notification via Telegram."""
        success, error = await self.telegram_service.send_notification(
            merchant=merchant,
            event=event,
            event_type=event_type
        )

        if success:
            self._stats["telegram_sent"] += 1
            logger.info(f"Telegram notification sent to {merchant.short_id()}")
        else:
            self._stats["telegram_failed"] += 1
            logger.warning(f"Telegram notification failed for {merchant.short_id()}: {error}")

        return success, error

    async def broadcast_to_all(
        self,
        event: PaymentEvent,
        event_type: str = "payment.completed"
    ) -> Dict[str, bool]:
        """
        Send notification about an event to all registered merchants.

        Useful for testing or system-wide notifications.

        Args:
            event: Payment event
            event_type: Event type

        Returns:
            Dictionary of merchant_id -> success
        """
        merchants = await self.db.get_active_merchants()
        results = {}

        for merchant_data in merchants:
            merchant = Merchant.from_dict(merchant_data)
            success, _ = await self.route_notification(
                PaymentEvent(
                    payment_intent_id=event.payment_intent_id,
                    merchant_id=merchant.id,  # Override with each merchant
                    customer_address=event.customer_address,
                    token_address=event.token_address,
                    amount=event.amount,
                    transaction_hash=event.transaction_hash,
                    block_number=event.block_number,
                    block_timestamp=event.block_timestamp
                ),
                event_type
            )
            results[merchant.id] = success

        return results

    async def notify_multiple(
        self,
        events: List[PaymentEvent],
        event_type: str = "payment.completed"
    ) -> List[Tuple[str, bool, Optional[str]]]:
        """
        Send notifications for multiple events.

        Args:
            events: List of payment events
            event_type: Event type

        Returns:
            List of (payment_id, success, error) tuples
        """
        results = []

        # Process in batches to avoid overwhelming services
        batch_size = 10

        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]

            # Process batch concurrently
            tasks = [
                self.route_notification(event, event_type)
                for event in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for event, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results.append((event.payment_intent_id, False, str(result)))
                else:
                    success, error = result
                    results.append((event.payment_intent_id, success, error))

            # Small delay between batches
            if i + batch_size < len(events):
                await asyncio.sleep(0.5)

        return results

    def get_stats(self) -> Dict[str, int]:
        """
        Get notification statistics.

        Returns:
            Statistics dictionary
        """
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self._stats:
            self._stats[key] = 0

    async def get_status(self) -> Dict:
        """
        Get router status.

        Returns:
            Status dictionary
        """
        return {
            "running": self._running,
            "stats": self.get_stats(),
            "webhook_service": await self.webhook_service.get_delivery_stats(),
            "telegram_service": await self.telegram_service.get_status()
        }
