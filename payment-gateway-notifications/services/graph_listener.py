"""
The Graph Listener Service.

Polls The Graph subgraph for PaymentExecuted events and processes them.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, List, Optional

import aiohttp

from config import config
from models.payment import PaymentEvent
from database.db import Database

logger = logging.getLogger(__name__)


# GraphQL query for fetching payment events
PAYMENT_EVENTS_QUERY = """
query GetPaymentEvents($lastBlock: BigInt!, $first: Int!) {
    paymentExecuteds(
        where: { blockNumber_gt: $lastBlock }
        orderBy: blockNumber
        orderDirection: asc
        first: $first
    ) {
        id
        paymentIntentId
        merchant
        customer
        token
        amount
        transactionHash
        blockNumber
        blockTimestamp
    }
}
"""

# Alternative query if your subgraph uses different field names
PAYMENT_EVENTS_QUERY_ALT = """
query GetPaymentEvents($lastBlock: BigInt!, $first: Int!) {
    payments(
        where: { blockNumber_gt: $lastBlock }
        orderBy: blockNumber
        orderDirection: asc
        first: $first
    ) {
        id
        paymentIntentId
        merchantId
        customerAddress
        tokenAddress
        amount
        txHash
        blockNumber
        timestamp
    }
}
"""


class GraphListener:
    """
    Service that listens to The Graph for payment events.

    Polls the subgraph at regular intervals and emits events
    for processing by the notification system.
    """

    def __init__(
        self,
        db: Database,
        subgraph_url: Optional[str] = None,
        polling_interval: int = 5
    ):
        """
        Initialize the Graph listener.

        Args:
            db: Database instance for persistence
            subgraph_url: The Graph subgraph endpoint URL
            polling_interval: Seconds between polls (default: 5)
        """
        self.db = db
        self.subgraph_url = subgraph_url or config.graph.url
        self.polling_interval = polling_interval
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._callbacks: List[Callable[[PaymentEvent], asyncio.Future]] = []
        self._last_block = 0
        self._use_alt_query = False

    def on_payment(self, callback: Callable[[PaymentEvent], asyncio.Future]) -> None:
        """
        Register a callback for payment events.

        Args:
            callback: Async function to call when payment is detected
        """
        self._callbacks.append(callback)
        logger.debug(f"Registered payment callback: {callback.__name__}")

    async def start(self) -> None:
        """Start the listener polling loop."""
        if self._running:
            logger.warning("Graph listener already running")
            return

        if not self.subgraph_url:
            raise ValueError("Subgraph URL is not configured")

        logger.info(f"Starting Graph listener (polling every {self.polling_interval}s)")
        logger.info(f"Subgraph URL: {self.subgraph_url}")

        self._running = True
        self._session = aiohttp.ClientSession()

        # Load last processed block from database
        self._last_block = await self.db.get_last_processed_block()
        logger.info(f"Resuming from block {self._last_block}")

        # Start polling loop
        asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the listener."""
        logger.info("Stopping Graph listener...")
        self._running = False

        if self._session:
            await self._session.close()
            self._session = None

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)

            # Wait before next poll
            await asyncio.sleep(self.polling_interval)

    async def _poll_once(self) -> None:
        """Execute a single poll for new events."""
        events = await self._fetch_events()

        if events:
            logger.info(f"Found {len(events)} new payment event(s)")

            for event in events:
                await self._process_event(event)

                # Update last processed block
                if event.block_number > self._last_block:
                    self._last_block = event.block_number
                    await self.db.update_last_processed_block(self._last_block)

    async def _fetch_events(self, limit: int = 100) -> List[PaymentEvent]:
        """
        Fetch payment events from The Graph.

        Args:
            limit: Maximum number of events to fetch

        Returns:
            List of PaymentEvent objects
        """
        if not self._session:
            return []

        query = PAYMENT_EVENTS_QUERY_ALT if self._use_alt_query else PAYMENT_EVENTS_QUERY

        variables = {
            "lastBlock": str(self._last_block),
            "first": limit
        }

        try:
            async with self._session.post(
                self.subgraph_url,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    logger.error(f"Graph API error: {response.status}")
                    return []

                data = await response.json()

                if "errors" in data:
                    errors = data["errors"]
                    logger.error(f"GraphQL errors: {errors}")

                    # Try alternative query if first one fails
                    if not self._use_alt_query and "Cannot query field" in str(errors):
                        logger.info("Switching to alternative query format")
                        self._use_alt_query = True
                        return await self._fetch_events(limit)

                    return []

                # Extract events from response
                result_data = data.get("data", {})

                # Handle different entity names
                events_raw = (
                    result_data.get("paymentExecuteds") or
                    result_data.get("payments") or
                    []
                )

                return [PaymentEvent.from_graph_data(e) for e in events_raw]

        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching events: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing events: {e}", exc_info=True)
            return []

    async def _process_event(self, event: PaymentEvent) -> None:
        """
        Process a single payment event.

        Args:
            event: PaymentEvent to process
        """
        logger.info(
            f"Processing payment: {event.short_payment_id()} "
            f"for merchant {event.short_merchant_address()} "
            f"amount: {event.get_formatted_amount()}"
        )

        # Save event to database
        try:
            await self.db.save_payment_event(
                payment_id=event.payment_intent_id,
                merchant_id=event.merchant_id,
                customer_address=event.customer_address,
                token_address=event.token_address,
                amount=event.amount,
                transaction_hash=event.transaction_hash,
                block_number=event.block_number,
                block_timestamp=event.block_timestamp
            )
        except Exception as e:
            logger.error(f"Error saving payment event: {e}")

        # Invoke callbacks
        for callback in self._callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in payment callback: {e}", exc_info=True)

    async def get_status(self) -> dict:
        """
        Get listener status.

        Returns:
            Status dictionary
        """
        return {
            "running": self._running,
            "subgraph_url": self.subgraph_url,
            "polling_interval": self.polling_interval,
            "last_block": self._last_block,
            "callbacks_registered": len(self._callbacks)
        }

    async def manual_poll(self) -> List[PaymentEvent]:
        """
        Manually trigger a poll (useful for testing).

        Returns:
            List of events found
        """
        if not self._session:
            self._session = aiohttp.ClientSession()

        return await self._fetch_events()

    async def set_start_block(self, block_number: int) -> None:
        """
        Set the starting block for polling.

        Useful for testing or catching up on historical events.

        Args:
            block_number: Block number to start from
        """
        self._last_block = block_number
        await self.db.update_last_processed_block(block_number)
        logger.info(f"Set starting block to {block_number}")
