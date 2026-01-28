#!/usr/bin/env python3
"""
Example: Simulate a payment event for testing.

This script simulates a payment event to test the notification system
without needing actual blockchain transactions.

Usage:
    python simulate_payment.py 0x1234...5678 100.50

Arguments:
    merchant_id: The merchant's Ethereum address
    amount: Payment amount in tokens (e.g., 100.50 USDC)
"""

import argparse
import asyncio
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from models.payment import PaymentEvent
from models.merchant import Merchant
from services.webhook_service import WebhookService
from services.telegram_service import TelegramService
from services.notification_router import NotificationRouter
from config import config


async def simulate_payment(
    merchant_id: str,
    amount: float,
    token_symbol: str = "USDC"
) -> None:
    """Simulate a payment event and send notification."""

    print(f"Simulating payment to {merchant_id[:10]}...{merchant_id[-4:]}")
    print(f"Amount: {amount} {token_symbol}")
    print()

    # Token addresses (Sepolia)
    token_addresses = {
        "USDC": "0x1c7d4b196cb0c7b01d743fbc6116a902379c7238",
        "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f"
    }

    token_decimals = {
        "USDC": 6,
        "USDT": 6,
        "DAI": 18
    }

    token_address = token_addresses.get(token_symbol, token_addresses["USDC"])
    decimals = token_decimals.get(token_symbol, 6)

    # Convert amount to smallest unit
    amount_raw = str(int(Decimal(str(amount)) * Decimal(10 ** decimals)))

    # Create simulated payment event
    import secrets
    event = PaymentEvent(
        payment_intent_id=f"pi_sim_{secrets.token_hex(8)}",
        merchant_id=merchant_id,
        customer_address=f"0x{''.join(secrets.choice('0123456789abcdef') for _ in range(40))}",
        token_address=token_address,
        amount=amount_raw,
        transaction_hash=f"0x{''.join(secrets.choice('0123456789abcdef') for _ in range(64))}",
        block_number=12345678,
        block_timestamp=datetime.utcnow()
    )

    print("Created simulated payment event:")
    print(f"  Payment ID: {event.payment_intent_id}")
    print(f"  Customer: {event.short_customer_address()}")
    print(f"  Amount: {event.get_formatted_amount()}")
    print(f"  TX Hash: {event.transaction_hash[:20]}...")
    print()

    # Initialize services
    print("Initializing services...")
    db = Database()
    await db.connect()

    # Check if merchant exists
    merchant_data = await db.get_merchant(merchant_id.lower())
    if not merchant_data:
        print(f"\n❌ Merchant {merchant_id[:10]}... not found!")
        print("   Register the merchant first using register_merchant.py")
        await db.disconnect()
        return

    merchant = Merchant.from_dict(merchant_data)
    print(f"  Found merchant: {merchant.name or merchant.short_id()}")
    print(f"  Notification type: {merchant.notification_type.value}")
    print()

    # Initialize notification services
    webhook_service = WebhookService(db)
    await webhook_service.start()

    telegram_service = TelegramService(db)
    await telegram_service.start()

    router = NotificationRouter(
        db=db,
        webhook_service=webhook_service,
        telegram_service=telegram_service
    )
    await router.start()

    # Send notification
    print("Sending notification...")
    success, error = await router.route_notification(event)

    if success:
        print("\n✅ Notification sent successfully!")
    else:
        print(f"\n❌ Notification failed: {error}")

    # Print stats
    stats = router.get_stats()
    print("\nRouter stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Cleanup
    await webhook_service.stop()
    await telegram_service.stop()
    await db.disconnect()


async def main():
    parser = argparse.ArgumentParser(
        description='Simulate a payment event for testing'
    )
    parser.add_argument(
        'merchant_id',
        help='Merchant Ethereum address (0x...)'
    )
    parser.add_argument(
        'amount',
        type=float,
        help='Payment amount (e.g., 100.50)'
    )
    parser.add_argument(
        '--token',
        default='USDC',
        choices=['USDC', 'USDT', 'DAI'],
        help='Token symbol (default: USDC)'
    )

    args = parser.parse_args()

    await simulate_payment(
        merchant_id=args.merchant_id,
        amount=args.amount,
        token_symbol=args.token
    )


if __name__ == '__main__':
    asyncio.run(main())
