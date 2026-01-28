-- =============================================================================
-- Payment Gateway Notifications - Database Schema
-- =============================================================================
-- This schema supports both PostgreSQL and SQLite with minor adaptations.
-- Run this script to initialize the database tables.

-- -----------------------------------------------------------------------------
-- Merchants Table
-- -----------------------------------------------------------------------------
-- Stores merchant information and their notification preferences.
-- Each merchant can choose either webhook or telegram notifications.

CREATE TABLE IF NOT EXISTS merchants (
    -- Merchant's Ethereum address (0x prefixed, 42 characters)
    id VARCHAR(42) PRIMARY KEY,

    -- Human-readable merchant name (optional)
    name VARCHAR(255),

    -- Notification delivery method: 'webhook' or 'telegram'
    notification_type VARCHAR(20) NOT NULL CHECK (notification_type IN ('webhook', 'telegram')),

    -- Webhook configuration (required if notification_type = 'webhook')
    webhook_url TEXT,

    -- Secret key for HMAC signature verification (auto-generated for webhook merchants)
    webhook_secret VARCHAR(64),

    -- Telegram chat ID (required if notification_type = 'telegram')
    -- Can be obtained by messaging the bot and using /start command
    telegram_chat_id VARCHAR(50),

    -- Whether merchant is actively receiving notifications
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamp when merchant was registered
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Timestamp of last update
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Validation constraints
    CONSTRAINT check_webhook_config CHECK (
        notification_type != 'webhook' OR (webhook_url IS NOT NULL AND webhook_secret IS NOT NULL)
    ),
    CONSTRAINT check_telegram_config CHECK (
        notification_type != 'telegram' OR telegram_chat_id IS NOT NULL
    )
);

-- Index for faster lookups by notification type
CREATE INDEX IF NOT EXISTS idx_merchants_notification_type ON merchants(notification_type);

-- Index for active merchants
CREATE INDEX IF NOT EXISTS idx_merchants_is_active ON merchants(is_active);


-- -----------------------------------------------------------------------------
-- Webhook Deliveries Table
-- -----------------------------------------------------------------------------
-- Logs all notification delivery attempts for auditing and retry management.

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    -- Auto-incrementing unique identifier
    id SERIAL PRIMARY KEY,

    -- Reference to the merchant
    merchant_id VARCHAR(42) NOT NULL REFERENCES merchants(id),

    -- Type of event (e.g., 'payment.completed', 'payment.failed')
    event_type VARCHAR(50) NOT NULL,

    -- Unique event identifier for deduplication
    event_id VARCHAR(100) NOT NULL,

    -- Delivery method used: 'webhook' or 'telegram'
    delivery_method VARCHAR(20) NOT NULL CHECK (delivery_method IN ('webhook', 'telegram')),

    -- Request payload (JSON)
    payload TEXT,

    -- Whether delivery was successful
    success BOOLEAN NOT NULL DEFAULT FALSE,

    -- HTTP response code (for webhooks) or API response code (for telegram)
    response_code INT,

    -- Response body or error message
    response_body TEXT,

    -- Number of retry attempts made
    retry_count INT DEFAULT 0,

    -- Next scheduled retry timestamp (NULL if no retry needed)
    next_retry_at TIMESTAMP,

    -- Timestamp when delivery was attempted
    delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Timestamp when delivery was created
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for finding pending retries
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_next_retry
    ON webhook_deliveries(next_retry_at)
    WHERE success = FALSE AND next_retry_at IS NOT NULL;

-- Index for merchant delivery history
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_merchant
    ON webhook_deliveries(merchant_id, delivered_at DESC);

-- Index for event deduplication
CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_deliveries_event_merchant
    ON webhook_deliveries(event_id, merchant_id);


-- -----------------------------------------------------------------------------
-- Processed Blocks Table
-- -----------------------------------------------------------------------------
-- Tracks the last processed block number for resuming after restart.

CREATE TABLE IF NOT EXISTS processed_blocks (
    -- Single row table, fixed key
    id VARCHAR(20) PRIMARY KEY DEFAULT 'last_block',

    -- Last successfully processed block number
    block_number BIGINT NOT NULL DEFAULT 0,

    -- Timestamp of last update
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initialize with default value
INSERT INTO processed_blocks (id, block_number)
VALUES ('last_block', 0)
ON CONFLICT (id) DO NOTHING;


-- -----------------------------------------------------------------------------
-- Payment Events Table (Optional - for local caching/history)
-- -----------------------------------------------------------------------------
-- Stores processed payment events for reference and debugging.

CREATE TABLE IF NOT EXISTS payment_events (
    -- Unique payment intent ID from the smart contract
    id VARCHAR(100) PRIMARY KEY,

    -- Merchant who received the payment
    merchant_id VARCHAR(42) NOT NULL,

    -- Customer's wallet address
    customer_address VARCHAR(42) NOT NULL,

    -- Token contract address (e.g., USDC)
    token_address VARCHAR(42) NOT NULL,

    -- Payment amount (in token's smallest unit, e.g., wei)
    amount VARCHAR(78) NOT NULL,

    -- Transaction hash on blockchain
    transaction_hash VARCHAR(66) NOT NULL,

    -- Block number where transaction was mined
    block_number BIGINT NOT NULL,

    -- Block timestamp
    block_timestamp TIMESTAMP NOT NULL,

    -- Whether notification was successfully sent
    notification_sent BOOLEAN DEFAULT FALSE,

    -- Timestamp when event was processed
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for finding unnotified events
CREATE INDEX IF NOT EXISTS idx_payment_events_notification
    ON payment_events(notification_sent)
    WHERE notification_sent = FALSE;

-- Index for merchant payment history
CREATE INDEX IF NOT EXISTS idx_payment_events_merchant
    ON payment_events(merchant_id, block_timestamp DESC);


-- -----------------------------------------------------------------------------
-- Utility Views
-- -----------------------------------------------------------------------------

-- View: Active webhook merchants
CREATE VIEW IF NOT EXISTS active_webhook_merchants AS
SELECT id, name, webhook_url, webhook_secret, created_at
FROM merchants
WHERE notification_type = 'webhook' AND is_active = TRUE;

-- View: Active telegram merchants
CREATE VIEW IF NOT EXISTS active_telegram_merchants AS
SELECT id, name, telegram_chat_id, created_at
FROM merchants
WHERE notification_type = 'telegram' AND is_active = TRUE;

-- View: Recent delivery failures (last 24 hours)
CREATE VIEW IF NOT EXISTS recent_delivery_failures AS
SELECT
    wd.id,
    wd.merchant_id,
    m.name as merchant_name,
    wd.event_type,
    wd.delivery_method,
    wd.response_code,
    wd.retry_count,
    wd.delivered_at
FROM webhook_deliveries wd
JOIN merchants m ON wd.merchant_id = m.id
WHERE wd.success = FALSE
  AND wd.delivered_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY wd.delivered_at DESC;
