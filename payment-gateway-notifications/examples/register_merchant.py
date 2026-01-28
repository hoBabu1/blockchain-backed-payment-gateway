#!/usr/bin/env python3
"""
Example: Register a merchant for notifications.

This script demonstrates how to register merchants
for either webhook or Telegram notifications.

Usage:
    # Register webhook merchant
    python register_merchant.py webhook 0x1234...5678 https://your-site.com/webhook

    # Register Telegram merchant
    python register_merchant.py telegram 0x1234...5678 123456789

    # With name
    python register_merchant.py webhook 0x1234...5678 https://your-site.com/webhook --name "My Shop"
"""

import argparse
import asyncio
import json
import sys
import aiohttp


async def register_webhook_merchant(
    api_url: str,
    merchant_id: str,
    webhook_url: str,
    name: str = None
) -> dict:
    """Register a webhook merchant."""
    payload = {
        "merchant_id": merchant_id,
        "notification_type": "webhook",
        "webhook_url": webhook_url
    }
    if name:
        payload["name"] = name

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{api_url}/api/merchant/register",
            json=payload
        ) as response:
            return await response.json()


async def register_telegram_merchant(
    api_url: str,
    merchant_id: str,
    telegram_chat_id: str,
    name: str = None
) -> dict:
    """Register a Telegram merchant."""
    payload = {
        "merchant_id": merchant_id,
        "notification_type": "telegram",
        "telegram_chat_id": telegram_chat_id
    }
    if name:
        payload["name"] = name

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{api_url}/api/merchant/register",
            json=payload
        ) as response:
            return await response.json()


async def main():
    parser = argparse.ArgumentParser(
        description='Register a merchant for payment notifications'
    )
    parser.add_argument(
        'type',
        choices=['webhook', 'telegram'],
        help='Notification type'
    )
    parser.add_argument(
        'merchant_id',
        help='Merchant Ethereum address (0x...)'
    )
    parser.add_argument(
        'endpoint',
        help='Webhook URL or Telegram chat ID'
    )
    parser.add_argument(
        '--name',
        help='Merchant name (optional)'
    )
    parser.add_argument(
        '--api-url',
        default='http://localhost:8000',
        help='API server URL (default: http://localhost:8000)'
    )

    args = parser.parse_args()

    print(f"Registering {args.type} merchant...")
    print(f"  Merchant ID: {args.merchant_id}")
    print(f"  Endpoint: {args.endpoint}")
    if args.name:
        print(f"  Name: {args.name}")
    print()

    try:
        if args.type == 'webhook':
            result = await register_webhook_merchant(
                api_url=args.api_url,
                merchant_id=args.merchant_id,
                webhook_url=args.endpoint,
                name=args.name
            )
        else:
            result = await register_telegram_merchant(
                api_url=args.api_url,
                merchant_id=args.merchant_id,
                telegram_chat_id=args.endpoint,
                name=args.name
            )

        print("Response:")
        print(json.dumps(result, indent=2))

        if result.get('success'):
            print("\n✅ Merchant registered successfully!")

            if args.type == 'webhook':
                secret = result.get('merchant', {}).get('webhook_secret')
                if secret:
                    print(f"\n⚠️  IMPORTANT: Save your webhook secret:")
                    print(f"   {secret}")
                    print("\n   You'll need this to verify webhook signatures.")
        else:
            print(f"\n❌ Registration failed: {result.get('error')}")
            sys.exit(1)

    except aiohttp.ClientError as e:
        print(f"\n❌ Connection error: {e}")
        print("   Make sure the API server is running.")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
