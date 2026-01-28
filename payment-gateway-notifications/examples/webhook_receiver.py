#!/usr/bin/env python3
"""
Example: Webhook Receiver for Merchants

This script demonstrates how a merchant would receive and verify
webhook notifications from the payment gateway.

Usage:
    python webhook_receiver.py --secret YOUR_WEBHOOK_SECRET --port 5000

The script will:
1. Start a local web server
2. Listen for webhook POST requests
3. Verify the HMAC signature
4. Display the payment details
"""

import argparse
import hashlib
import hmac
import json
from datetime import datetime

from aiohttp import web


def verify_signature(payload_json: str, signature: str, secret: str) -> bool:
    """
    Verify the webhook signature.

    Args:
        payload_json: Raw JSON payload (without signature field)
        signature: Signature from X-Webhook-Signature header
        secret: Your webhook secret

    Returns:
        True if signature is valid
    """
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]

    # Parse payload and remove signature field for verification
    payload = json.loads(payload_json)
    payload.pop('signature', None)

    # Re-serialize with consistent formatting
    payload_to_verify = json.dumps(payload, separators=(',', ':'), sort_keys=True)

    # Calculate expected signature
    expected = hmac.new(
        secret.encode('utf-8'),
        payload_to_verify.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def handle_webhook(request: web.Request) -> web.Response:
    """Handle incoming webhook requests."""
    secret = request.app['webhook_secret']

    # Get signature from header
    signature = request.headers.get('X-Webhook-Signature', '')
    event_type = request.headers.get('X-Webhook-Event', 'unknown')
    event_id = request.headers.get('X-Webhook-ID', 'unknown')

    print("\n" + "=" * 60)
    print(f"📨 Received webhook at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Read body
    try:
        body = await request.text()
        payload = json.loads(body)
    except Exception as e:
        print(f"❌ Error parsing body: {e}")
        return web.json_response({"error": "Invalid JSON"}, status=400)

    # Verify signature
    if secret:
        is_valid = verify_signature(body, signature, secret)
        if is_valid:
            print("✅ Signature verified!")
        else:
            print("❌ SIGNATURE VERIFICATION FAILED!")
            print("   This webhook may not be authentic.")
            # In production, you would reject this request
            # return web.json_response({"error": "Invalid signature"}, status=401)
    else:
        print("⚠️  No secret configured - skipping signature verification")

    # Display webhook details
    print(f"\nEvent Type: {event_type}")
    print(f"Event ID: {event_id}")

    # Display payment data
    data = payload.get('data', {})
    print("\n💰 Payment Details:")
    print(f"   Payment Intent ID: {data.get('payment_intent_id')}")
    print(f"   Merchant ID: {data.get('merchant_id')}")
    print(f"   Customer: {data.get('customer_address')}")
    print(f"   Amount: {data.get('formatted_amount', data.get('amount'))}")
    print(f"   Token: {data.get('token_address')}")
    print(f"   TX Hash: {data.get('transaction_hash')}")
    print(f"   Block: {data.get('block_number')}")
    print(f"   Status: {data.get('status')}")

    print("\n📋 Full Payload:")
    print(json.dumps(payload, indent=2))

    # In a real implementation, you would:
    # 1. Store the payment in your database
    # 2. Update order status
    # 3. Trigger fulfillment
    # 4. Send confirmation to customer

    print("\n" + "-" * 60)
    print("✅ Webhook processed successfully!")
    print("-" * 60)

    return web.json_response({"status": "received"})


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "healthy"})


def create_app(webhook_secret: str) -> web.Application:
    """Create the webhook receiver application."""
    app = web.Application()
    app['webhook_secret'] = webhook_secret

    app.router.add_post('/webhook', handle_webhook)
    app.router.add_post('/api/payments', handle_webhook)  # Alternative path
    app.router.add_get('/health', handle_health)

    return app


async def main():
    parser = argparse.ArgumentParser(
        description='Webhook receiver for testing payment notifications'
    )
    parser.add_argument(
        '--secret',
        default='',
        help='Webhook secret for signature verification'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to listen on (default: 5000)'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )

    args = parser.parse_args()

    app = create_app(args.secret)

    print("=" * 60)
    print("🚀 Webhook Receiver Started")
    print("=" * 60)
    print(f"Listening on: http://{args.host}:{args.port}")
    print(f"Webhook endpoint: http://{args.host}:{args.port}/webhook")
    print(f"Secret configured: {'Yes' if args.secret else 'No'}")
    print()
    print("To test with ngrok:")
    print(f"  ngrok http {args.port}")
    print()
    print("Then register your merchant with the ngrok URL:")
    print("  python register_merchant.py webhook 0x... https://YOUR_NGROK_URL/webhook")
    print("=" * 60)
    print("\nWaiting for webhooks...")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, args.host, args.port)
    await site.start()

    # Run forever
    import asyncio
    await asyncio.Event().wait()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
