"""
Telegram Notification Service.

Handles sending payment notifications to merchants via Telegram bot.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config import config
from database.db import Database
from models.merchant import Merchant
from models.payment import PaymentEvent, TelegramMessage

logger = logging.getLogger(__name__)


class TelegramService:
    """
    Service for sending Telegram notifications to merchants.

    Features:
    - Formatted messages with payment details
    - Transaction links to block explorer
    - Rate limiting to comply with Telegram API limits
    - Retry logic for failed deliveries
    """

    # Telegram API limits: 30 messages per second to different chats
    # We'll be conservative and limit to 20 per second
    RATE_LIMIT = 20
    RATE_PERIOD = 1.0  # seconds

    def __init__(
        self,
        db: Database,
        bot_token: Optional[str] = None,
        etherscan_url: Optional[str] = None
    ):
        """
        Initialize the Telegram service.

        Args:
            db: Database instance for logging deliveries
            bot_token: Telegram bot token from @BotFather
            etherscan_url: Block explorer URL for transaction links
        """
        self.db = db
        self.bot_token = bot_token or config.telegram.bot_token
        self.etherscan_url = etherscan_url or config.network.etherscan_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._last_send_times: List[float] = []

    @property
    def api_url(self) -> str:
        """Get Telegram Bot API base URL."""
        return f"https://api.telegram.org/bot{self.bot_token}"

    async def start(self) -> None:
        """Start the Telegram service."""
        if not self.bot_token:
            raise ValueError("Telegram bot token is not configured")

        logger.info("Starting Telegram notification service...")
        self._session = aiohttp.ClientSession()
        self._running = True

        # Verify bot token
        if await self._verify_bot():
            logger.info("Telegram bot verified successfully")
        else:
            logger.error("Failed to verify Telegram bot token")

        # Start message processor
        asyncio.create_task(self._message_processor())

        # Start retry processor
        asyncio.create_task(self._retry_processor())

        logger.info("Telegram service started")

    async def stop(self) -> None:
        """Stop the Telegram service."""
        logger.info("Stopping Telegram service...")
        self._running = False

        if self._session:
            await self._session.close()
            self._session = None

    async def _verify_bot(self) -> bool:
        """Verify the bot token by calling getMe."""
        try:
            async with self._session.get(f"{self.api_url}/getMe") as response:
                data = await response.json()
                if data.get('ok'):
                    bot_info = data.get('result', {})
                    logger.info(
                        f"Bot verified: @{bot_info.get('username')} "
                        f"({bot_info.get('first_name')})"
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"Error verifying bot: {e}")
            return False

    async def send_notification(
        self,
        merchant: Merchant,
        event: PaymentEvent,
        event_type: str = "payment.completed"
    ) -> Tuple[bool, Optional[str]]:
        """
        Send a Telegram notification to a merchant.

        Args:
            merchant: Merchant to notify
            event: Payment event data
            event_type: Type of event

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if not merchant.is_telegram():
            return False, "Merchant is not configured for Telegram notifications"

        if not merchant.telegram_chat_id:
            return False, "Telegram chat ID not configured"

        # Format message
        telegram_msg = TelegramMessage(
            payment_event=event,
            etherscan_url=self.etherscan_url
        )
        message_text = telegram_msg.format()

        logger.info(
            f"Sending Telegram notification to {merchant.short_id()} "
            f"(chat: {merchant.telegram_chat_id})"
        )

        # Send message
        success, response = await self._send_message(
            chat_id=merchant.telegram_chat_id,
            text=message_text,
            parse_mode="Markdown"
        )

        # Generate event ID for logging
        event_id = event.get_event_id()

        # Log delivery
        next_retry = None
        if not success:
            next_retry = datetime.utcnow() + timedelta(minutes=1)

        await self.db.log_delivery(
            merchant_id=merchant.id,
            event_type=event_type,
            event_id=event_id,
            delivery_method='telegram',
            payload=message_text,
            success=success,
            response_code=response.get('error_code') if not success else 200,
            response_body=str(response),
            retry_count=0,
            next_retry_at=next_retry
        )

        if success:
            logger.info(f"Telegram notification sent to {merchant.short_id()}")
            return True, None
        else:
            error_msg = response.get('description', 'Unknown error')
            logger.warning(
                f"Telegram notification failed for {merchant.short_id()}: {error_msg}"
            )
            return False, error_msg

    async def _send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "Markdown"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Send a message via Telegram API.

        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Message formatting mode

        Returns:
            Tuple of (success, response_data)
        """
        if not self._session:
            return False, {"description": "Session not initialized"}

        # Rate limiting
        await self._apply_rate_limit()

        try:
            async with self._session.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": False
                }
            ) as response:
                data = await response.json()

                if data.get('ok'):
                    return True, data.get('result', {})
                else:
                    return False, data

        except aiohttp.ClientError as e:
            logger.error(f"Network error sending Telegram message: {e}")
            return False, {"description": str(e)}
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False, {"description": str(e)}

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting for Telegram API."""
        now = asyncio.get_event_loop().time()

        # Remove old timestamps
        self._last_send_times = [
            t for t in self._last_send_times
            if now - t < self.RATE_PERIOD
        ]

        # If at limit, wait
        if len(self._last_send_times) >= self.RATE_LIMIT:
            wait_time = self._last_send_times[0] + self.RATE_PERIOD - now
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        # Record this send
        self._last_send_times.append(now)

    async def _message_processor(self) -> None:
        """Process queued messages (for batch sending)."""
        while self._running:
            try:
                # Process any queued messages
                while not self._message_queue.empty():
                    msg = await self._message_queue.get()
                    await self._send_message(**msg)
            except Exception as e:
                logger.error(f"Error in message processor: {e}")

            await asyncio.sleep(0.1)

    async def _retry_processor(self) -> None:
        """Process failed Telegram deliveries for retry."""
        logger.info("Starting Telegram retry processor")

        while self._running:
            try:
                await self._process_retries()
            except Exception as e:
                logger.error(f"Error in Telegram retry processor: {e}", exc_info=True)

            await asyncio.sleep(60)  # Check every minute

    async def _process_retries(self) -> None:
        """Process pending Telegram retries."""
        pending = await self.db.get_pending_retries()

        # Filter to only telegram deliveries
        telegram_retries = [
            p for p in pending
            if p.get('delivery_method') == 'telegram'
        ]

        if telegram_retries:
            logger.info(f"Processing {len(telegram_retries)} Telegram retries")

        for delivery in telegram_retries:
            await self._retry_delivery(delivery)

    async def _retry_delivery(self, delivery: Dict[str, Any]) -> None:
        """Retry a failed Telegram delivery."""
        delivery_id = delivery['id']
        chat_id = delivery.get('telegram_chat_id')
        message_text = delivery.get('payload')
        retry_count = delivery['retry_count']

        if not chat_id or not message_text:
            logger.error(f"Missing data for Telegram retry {delivery_id}")
            await self.db.update_delivery_retry(
                delivery_id=delivery_id,
                retry_count=retry_count + 1,
                next_retry_at=None,
                response_body="Missing Telegram configuration"
            )
            return

        logger.info(f"Retrying Telegram delivery {delivery_id} (attempt {retry_count + 1})")

        success, response = await self._send_message(
            chat_id=chat_id,
            text=message_text
        )

        if success:
            await self.db.mark_delivery_success(delivery_id)
            logger.info(f"Telegram retry successful for delivery {delivery_id}")
        else:
            new_retry_count = retry_count + 1

            # Max 3 retries for Telegram
            if new_retry_count < 3:
                next_retry = datetime.utcnow() + timedelta(minutes=5 * new_retry_count)
            else:
                next_retry = None
                logger.error(f"All Telegram retries exhausted for delivery {delivery_id}")

            await self.db.update_delivery_retry(
                delivery_id=delivery_id,
                retry_count=new_retry_count,
                next_retry_at=next_retry,
                response_code=response.get('error_code'),
                response_body=str(response)
            )

    async def send_test_message(self, chat_id: str) -> Tuple[bool, str]:
        """
        Send a test message to verify chat ID.

        Args:
            chat_id: Telegram chat ID to test

        Returns:
            Tuple of (success, message)
        """
        test_message = """
*Test Notification*

This is a test message from PaymentGateway.
If you received this, your Telegram notifications are configured correctly!

Your Chat ID: `{}`
        """.format(chat_id)

        success, response = await self._send_message(
            chat_id=chat_id,
            text=test_message
        )

        if success:
            return True, "Test message sent successfully!"
        else:
            return False, f"Failed to send: {response.get('description', 'Unknown error')}"

    async def get_chat_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a chat.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Chat information or None if not found
        """
        try:
            async with self._session.post(
                f"{self.api_url}/getChat",
                json={"chat_id": chat_id}
            ) as response:
                data = await response.json()
                if data.get('ok'):
                    return data.get('result')
                return None
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            return None

    async def get_updates(self, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get bot updates (for debugging/setup).

        This can be used to find chat IDs of users who message the bot.

        Args:
            offset: Update offset

        Returns:
            List of updates
        """
        try:
            async with self._session.post(
                f"{self.api_url}/getUpdates",
                json={"offset": offset, "limit": 100}
            ) as response:
                data = await response.json()
                if data.get('ok'):
                    return data.get('result', [])
                return []
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []

    async def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "service": "telegram",
            "running": self._running,
            "bot_configured": bool(self.bot_token),
            "etherscan_url": self.etherscan_url
        }
