#!/usr/bin/env python3
"""
Example: Get Telegram Chat ID

This script helps merchants find their Telegram chat ID
by listening to updates from the bot.

Usage:
    python get_telegram_chat_id.py YOUR_BOT_TOKEN

Steps:
1. Create a bot with @BotFather on Telegram
2. Get your bot token
3. Run this script with your bot token
4. Send /start to your bot in Telegram
5. The script will show your chat ID
"""

import argparse
import asyncio
import aiohttp


async def get_updates(bot_token: str) -> list:
    """Get bot updates from Telegram API."""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if data.get('ok'):
                return data.get('result', [])
            else:
                print(f"Error: {data.get('description')}")
                return []


async def verify_bot(bot_token: str) -> dict:
    """Verify bot token and get bot info."""
    url = f"https://api.telegram.org/bot{bot_token}/getMe"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if data.get('ok'):
                return data.get('result')
            return None


async def send_test_message(bot_token: str, chat_id: str) -> bool:
    """Send a test message to verify chat ID."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": "✅ *Test successful!*\n\nYour Telegram notifications are configured correctly.\n\nYour Chat ID: `{}`".format(chat_id),
        "parse_mode": "Markdown"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            data = await response.json()
            return data.get('ok', False)


async def main():
    parser = argparse.ArgumentParser(
        description='Get your Telegram chat ID for payment notifications'
    )
    parser.add_argument(
        'bot_token',
        help='Your Telegram bot token from @BotFather'
    )
    parser.add_argument(
        '--send-test',
        metavar='CHAT_ID',
        help='Send a test message to verify a chat ID'
    )

    args = parser.parse_args()

    # If testing a specific chat ID
    if args.send_test:
        print(f"Sending test message to chat ID: {args.send_test}")
        success = await send_test_message(args.bot_token, args.send_test)
        if success:
            print("✅ Test message sent successfully!")
        else:
            print("❌ Failed to send test message. Check your chat ID.")
        return

    # Verify bot
    print("Verifying bot token...")
    bot_info = await verify_bot(args.bot_token)

    if not bot_info:
        print("\n❌ Invalid bot token!")
        print("   Make sure you copied the token correctly from @BotFather")
        return

    print(f"\n✅ Bot verified!")
    print(f"   Bot name: {bot_info.get('first_name')}")
    print(f"   Username: @{bot_info.get('username')}")

    print("\n" + "=" * 60)
    print("📱 HOW TO GET YOUR CHAT ID")
    print("=" * 60)
    print(f"1. Open Telegram and search for: @{bot_info.get('username')}")
    print("2. Start a conversation with the bot (click Start or send /start)")
    print("3. Wait a few seconds and press Enter here...")
    print("=" * 60)

    input("\nPress Enter after messaging the bot...")

    print("\nChecking for updates...")
    updates = await get_updates(args.bot_token)

    if not updates:
        print("\n⚠️  No messages found!")
        print("   Make sure you:")
        print("   1. Sent a message to the bot (not to @BotFather)")
        print("   2. The message was sent recently")
        print("   Try again after sending /start to your bot.")
        return

    # Extract unique chat IDs
    chat_ids = {}
    for update in updates:
        message = update.get('message', {})
        chat = message.get('chat', {})
        chat_id = chat.get('id')
        username = chat.get('username', 'N/A')
        first_name = chat.get('first_name', 'N/A')
        chat_type = chat.get('type', 'private')

        if chat_id:
            chat_ids[chat_id] = {
                'username': username,
                'first_name': first_name,
                'type': chat_type
            }

    print("\n" + "=" * 60)
    print("📋 FOUND CHAT IDS")
    print("=" * 60)

    for chat_id, info in chat_ids.items():
        print(f"\n  Chat ID: {chat_id}")
        print(f"  Name: {info['first_name']}")
        print(f"  Username: @{info['username']}")
        print(f"  Type: {info['type']}")

    print("\n" + "=" * 60)
    print("📝 NEXT STEPS")
    print("=" * 60)
    print("Use your Chat ID to register as a merchant:")
    print()
    print(f"  python register_merchant.py telegram 0xYOUR_ADDRESS {list(chat_ids.keys())[0]}")
    print()
    print("Or via API:")
    print('''
  curl -X POST http://localhost:8000/api/merchant/register \\
    -H "Content-Type: application/json" \\
    -d '{
      "merchant_id": "0xYOUR_ETHEREUM_ADDRESS",
      "notification_type": "telegram",
      "telegram_chat_id": "''' + str(list(chat_ids.keys())[0]) + '''"
    }'
''')


if __name__ == '__main__':
    asyncio.run(main())
