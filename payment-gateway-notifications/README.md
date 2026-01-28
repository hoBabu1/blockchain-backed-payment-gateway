# Payment Gateway Notifications

A dual notification system for blockchain payment gateways that sends payment notifications to merchants via **Webhooks** (for tech-savvy merchants) and **Telegram** (for non-technical merchants).

## Features

- **Dual Notification Methods**: Choose between Webhook or Telegram notifications
- **The Graph Integration**: Polls subgraph for `PaymentExecuted` events
- **HMAC Signature Verification**: Secure webhook payloads with SHA-256 signatures
- **Retry Logic**: Automatic retries for failed deliveries (1min, 5min, 15min, 1hr)
- **Rate Limiting**: Complies with Telegram API limits
- **Delivery Logging**: Complete audit trail of all notifications
- **REST API**: Easy merchant registration and management
- **Production Ready**: Clean shutdown, error handling, and logging

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Payment Gateway Notifications                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │   The Graph  │───▶│  Graph Listener  │───▶│  Notification │ │
│  │   Subgraph   │    │   (Polling)      │    │    Router     │ │
│  └──────────────┘    └──────────────────┘    └───────┬───────┘ │
│                                                       │         │
│                           ┌───────────────────────────┼───────┐ │
│                           │                           │       │ │
│                           ▼                           ▼       │ │
│                    ┌─────────────┐            ┌───────────┐   │ │
│                    │   Webhook   │            │  Telegram │   │ │
│                    │   Service   │            │  Service  │   │ │
│                    └──────┬──────┘            └─────┬─────┘   │ │
│                           │                         │         │ │
│                           ▼                         ▼         │ │
│                    ┌─────────────┐            ┌───────────┐   │ │
│                    │  Merchant   │            │  Merchant │   │ │
│                    │   Server    │            │  Telegram │   │ │
│                    └─────────────┘            └───────────┘   │ │
│                                                               │ │
├───────────────────────────────────────────────────────────────┤ │
│                        REST API                               │ │
│  POST /api/merchant/register  - Register merchant             │ │
│  GET  /api/merchant/{id}      - Get merchant details          │ │
│  PUT  /api/merchant/{id}      - Update merchant               │ │
│  DELETE /api/merchant/{id}    - Deactivate merchant           │ │
│  POST /api/merchant/{id}/test - Send test notification        │ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Clone or navigate to the project
cd payment-gateway-notifications

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your values
nano .env
```

Required configuration:

```env
# The Graph subgraph URL
SUBGRAPH_URL=https://api.studio.thegraph.com/query/YOUR_ID/YOUR_SUBGRAPH/version/latest

# Telegram bot token (from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Database (PostgreSQL for production, SQLite for development)
DATABASE_URL=sqlite:///./payment_notifications.db
```

### 3. Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow instructions to name your bot
4. Copy the bot token to your `.env` file

### 4. Run the Service

```bash
python main.py
```

The service will:
- Start the API server on `http://localhost:8000`
- Begin polling The Graph for payment events
- Process and route notifications to registered merchants

## Merchant Registration

### Register a Webhook Merchant

```bash
curl -X POST http://localhost:8000/api/merchant/register \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "0x1234567890123456789012345678901234567890",
    "notification_type": "webhook",
    "webhook_url": "https://your-shop.com/api/payments",
    "name": "My Shop"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Merchant registered successfully. Save your webhook_secret...",
  "merchant": {
    "id": "0x1234567890123456789012345678901234567890",
    "notification_type": "webhook",
    "webhook_url": "https://your-shop.com/api/payments",
    "webhook_secret": "a1b2c3d4e5f6...",
    "name": "My Shop",
    "is_active": true
  }
}
```

**Important**: Save the `webhook_secret` - you'll need it to verify webhook signatures!

### Register a Telegram Merchant

First, get your Telegram chat ID:

```bash
python examples/get_telegram_chat_id.py YOUR_BOT_TOKEN
```

Then register:

```bash
curl -X POST http://localhost:8000/api/merchant/register \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "0x1234567890123456789012345678901234567890",
    "notification_type": "telegram",
    "telegram_chat_id": "123456789",
    "name": "My Shop"
  }'
```

## Webhook Integration Guide

### Webhook Payload Format

```json
{
  "event_id": "evt_0xabc123_pi_xyz789",
  "event_type": "payment.completed",
  "timestamp": "2024-01-28T10:30:45Z",
  "data": {
    "payment_intent_id": "pi_xyz789",
    "merchant_id": "0x1234...",
    "customer_address": "0x5678...",
    "token_address": "0xUSDC...",
    "amount": "100000000",
    "formatted_amount": "100.00 USDC",
    "transaction_hash": "0xdef456...",
    "block_number": 12345678,
    "status": "completed"
  },
  "signature": "sha256_hmac_signature"
}
```

### Webhook Headers

| Header | Description |
|--------|-------------|
| `X-Webhook-Signature` | HMAC-SHA256 signature (`sha256=...`) |
| `X-Webhook-Event` | Event type (e.g., `payment.completed`) |
| `X-Webhook-ID` | Unique event identifier |
| `X-Webhook-Timestamp` | When the webhook was sent |

### Signature Verification (Python)

```python
import hmac
import hashlib
import json

def verify_webhook(payload_json: str, signature: str, secret: str) -> bool:
    """Verify webhook signature."""
    if signature.startswith('sha256='):
        signature = signature[7:]

    payload = json.loads(payload_json)
    payload.pop('signature', None)
    payload_to_verify = json.dumps(payload, separators=(',', ':'), sort_keys=True)

    expected = hmac.new(
        secret.encode('utf-8'),
        payload_to_verify.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)

# Usage in your webhook handler
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Webhook-Signature')

    if not verify_webhook(request.data.decode(), signature, WEBHOOK_SECRET):
        return 'Invalid signature', 401

    # Process the payment...
    return 'OK', 200
```

### Signature Verification (JavaScript/Node.js)

```javascript
const crypto = require('crypto');

function verifyWebhook(payloadJson, signature, secret) {
    if (signature.startsWith('sha256=')) {
        signature = signature.slice(7);
    }

    const payload = JSON.parse(payloadJson);
    delete payload.signature;
    const payloadToVerify = JSON.stringify(payload);

    const expected = crypto
        .createHmac('sha256', secret)
        .update(payloadToVerify)
        .digest('hex');

    return crypto.timingSafeEqual(
        Buffer.from(expected),
        Buffer.from(signature)
    );
}
```

## Telegram Notification Format

Merchants receive formatted messages like:

```
🎉 Payment Received!

💰 Amount: 100.00 USDC
👤 Customer: 0x1234...5678
📝 Payment ID: pi_abc123

🔗 View Transaction
https://sepolia.etherscan.io/tx/0x...

⏰ Time: 2024-01-28 10:30:45 UTC
📦 Block: #12345678

---
Powered by PaymentGateway
```

## Testing

### Run Unit Tests

```bash
pytest tests/ -v
```

### Test Webhook Receiver

Start the test webhook receiver:

```bash
python examples/webhook_receiver.py --secret YOUR_WEBHOOK_SECRET --port 5000
```

Use [ngrok](https://ngrok.com) to expose locally:

```bash
ngrok http 5000
```

Register with the ngrok URL and simulate a payment.

### Simulate a Payment

```bash
python examples/simulate_payment.py 0xYOUR_MERCHANT_ADDRESS 100.50
```

### Test Telegram Notifications

```bash
python examples/get_telegram_chat_id.py YOUR_BOT_TOKEN --send-test YOUR_CHAT_ID
```

## API Reference

### POST /api/merchant/register

Register a new merchant.

**Request Body:**

```json
{
  "merchant_id": "0x...",
  "notification_type": "webhook" | "telegram",
  "name": "Shop Name (optional)",
  "webhook_url": "https://... (required for webhook)",
  "telegram_chat_id": "123456789 (required for telegram)"
}
```

### GET /api/merchant/{merchant_id}

Get merchant details (secrets are masked).

### PUT /api/merchant/{merchant_id}

Update merchant settings.

### DELETE /api/merchant/{merchant_id}

Deactivate merchant (soft delete).

### POST /api/merchant/{merchant_id}/test

Send a test notification to verify setup.

### GET /api/health

Health check endpoint.

### GET /api/stats

Get service statistics.

## Project Structure

```
payment-gateway-notifications/
├── main.py                    # Service orchestrator
├── config.py                  # Configuration management
├── .env.example               # Example environment file
├── requirements.txt           # Python dependencies
├── services/
│   ├── graph_listener.py      # The Graph polling
│   ├── webhook_service.py     # Webhook delivery + retry
│   ├── telegram_service.py    # Telegram notifications
│   └── notification_router.py # Routes to correct service
├── models/
│   ├── merchant.py            # Merchant data model
│   └── payment.py             # Payment & webhook models
├── database/
│   ├── db.py                  # Database connection
│   └── schema.sql             # Database schema
├── api/
│   └── merchant_api.py        # REST API endpoints
├── tests/
│   └── test_services.py       # Unit tests
└── examples/
    ├── register_merchant.py   # Registration script
    ├── simulate_payment.py    # Payment simulation
    ├── webhook_receiver.py    # Test webhook server
    └── get_telegram_chat_id.py # Get Telegram chat ID
```

## Database Schema

The service uses PostgreSQL (production) or SQLite (development).

### Tables

- **merchants**: Merchant registration and preferences
- **webhook_deliveries**: Notification delivery log
- **processed_blocks**: Last processed block tracking
- **payment_events**: Payment event history

See `database/schema.sql` for complete schema.

## Deployment

### Production Checklist

- [ ] Use PostgreSQL instead of SQLite
- [ ] Set `LOG_LEVEL=WARNING` or `ERROR`
- [ ] Configure proper `WEBHOOK_TIMEOUT` and retry delays
- [ ] Set up database backups
- [ ] Use environment variables (not `.env` file)
- [ ] Set up monitoring and alerting
- [ ] Use a process manager (systemd, supervisor)

### Docker (Example)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  notifications:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: payment_notifications
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## Troubleshooting

### Webhook not received

1. Check merchant is registered and active
2. Verify webhook URL is publicly accessible
3. Check delivery logs in database
4. Ensure your server returns 2xx status

### Telegram message not received

1. Make sure you started a conversation with the bot
2. Verify chat ID is correct
3. Check bot token is valid
4. Look for rate limit errors in logs

### Graph listener not finding events

1. Verify subgraph URL is correct
2. Check subgraph is synced
3. Verify event entity names match query
4. Check last processed block in database

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Format code: `black . && isort .`
6. Submit a pull request

## License

MIT License - see LICENSE file for details.
