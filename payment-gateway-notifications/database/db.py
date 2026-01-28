"""
Database connection and query module.

Provides a clean interface for database operations with support
for both PostgreSQL and SQLite backends.
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import aiosqlite

from config import config

logger = logging.getLogger(__name__)


class Database:
    """
    Async database connection manager.

    Supports PostgreSQL (production) and SQLite (development).
    Provides connection pooling and query execution methods.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_url: Database connection URL. Uses config if not provided.
        """
        self.database_url = database_url or config.database.url
        self._pool = None
        self._sqlite_conn = None
        self._is_postgres = self.database_url.startswith('postgresql')

    async def connect(self) -> None:
        """Establish database connection(s)."""
        if self._is_postgres:
            logger.info("Connecting to PostgreSQL database...")
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
        else:
            # SQLite for development
            db_path = self.database_url.replace('sqlite:///', '')
            logger.info(f"Connecting to SQLite database: {db_path}")
            self._sqlite_conn = await aiosqlite.connect(db_path)
            self._sqlite_conn.row_factory = aiosqlite.Row

        logger.info("Database connection established")

    async def disconnect(self) -> None:
        """Close database connection(s)."""
        if self._is_postgres and self._pool:
            await self._pool.close()
            self._pool = None
        elif self._sqlite_conn:
            await self._sqlite_conn.close()
            self._sqlite_conn = None

        logger.info("Database connection closed")

    async def execute(self, query: str, *args) -> str:
        """
        Execute a query without returning results.

        Args:
            query: SQL query to execute
            *args: Query parameters

        Returns:
            Status message from database
        """
        if self._is_postgres:
            async with self._pool.acquire() as conn:
                return await conn.execute(query, *args)
        else:
            await self._sqlite_conn.execute(query, args)
            await self._sqlite_conn.commit()
            return "OK"

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Execute a query and fetch one row.

        Args:
            query: SQL query to execute
            *args: Query parameters

        Returns:
            Row as dictionary or None if no results
        """
        if self._is_postgres:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        else:
            # Convert $1, $2 style params to ? for SQLite
            sqlite_query = self._convert_params(query)
            cursor = await self._sqlite_conn.execute(sqlite_query, args)
            row = await cursor.fetchone()
            if row:
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
            return None

    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        Execute a query and fetch all rows.

        Args:
            query: SQL query to execute
            *args: Query parameters

        Returns:
            List of rows as dictionaries
        """
        if self._is_postgres:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        else:
            sqlite_query = self._convert_params(query)
            cursor = await self._sqlite_conn.execute(sqlite_query, args)
            rows = await cursor.fetchall()
            if rows:
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            return []

    async def execute_many(self, query: str, args_list: List[Tuple]) -> None:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query to execute
            args_list: List of parameter tuples
        """
        if self._is_postgres:
            async with self._pool.acquire() as conn:
                await conn.executemany(query, args_list)
        else:
            sqlite_query = self._convert_params(query)
            await self._sqlite_conn.executemany(sqlite_query, args_list)
            await self._sqlite_conn.commit()

    def _convert_params(self, query: str) -> str:
        """Convert PostgreSQL $1, $2 style params to SQLite ? style."""
        import re
        # Replace $1, $2, etc. with ?
        return re.sub(r'\$\d+', '?', query)

    async def init_schema(self) -> None:
        """Initialize database schema from schema.sql file."""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

        with open(schema_path, 'r') as f:
            schema = f.read()

        # Split by semicolons and execute each statement
        statements = [s.strip() for s in schema.split(';') if s.strip()]

        for statement in statements:
            # Skip comments and empty lines
            if statement.startswith('--') or not statement:
                continue

            # Handle CREATE VIEW IF NOT EXISTS for SQLite
            if not self._is_postgres:
                statement = statement.replace('CREATE VIEW IF NOT EXISTS', 'CREATE VIEW IF NOT EXISTS')
                statement = statement.replace('SERIAL', 'INTEGER')
                statement = statement.replace('INTERVAL \'24 hours\'', "datetime('now', '-24 hours')")

            try:
                if self._is_postgres:
                    async with self._pool.acquire() as conn:
                        await conn.execute(statement)
                else:
                    await self._sqlite_conn.execute(statement)
            except Exception as e:
                # Log but continue - some statements may fail on re-run
                logger.debug(f"Schema statement skipped: {e}")

        if not self._is_postgres:
            await self._sqlite_conn.commit()

        logger.info("Database schema initialized")

    # -------------------------------------------------------------------------
    # Merchant Operations
    # -------------------------------------------------------------------------

    async def get_merchant(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        """Get merchant by ID."""
        return await self.fetch_one(
            "SELECT * FROM merchants WHERE id = $1",
            merchant_id
        )

    async def get_active_merchants(self) -> List[Dict[str, Any]]:
        """Get all active merchants."""
        return await self.fetch_all(
            "SELECT * FROM merchants WHERE is_active = TRUE"
        )

    async def create_merchant(
        self,
        merchant_id: str,
        notification_type: str,
        name: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        telegram_chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new merchant."""
        now = datetime.utcnow()

        if self._is_postgres:
            await self.execute(
                """
                INSERT INTO merchants (id, name, notification_type, webhook_url,
                                       webhook_secret, telegram_chat_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    notification_type = EXCLUDED.notification_type,
                    webhook_url = EXCLUDED.webhook_url,
                    webhook_secret = EXCLUDED.webhook_secret,
                    telegram_chat_id = EXCLUDED.telegram_chat_id,
                    updated_at = EXCLUDED.updated_at
                """,
                merchant_id, name, notification_type, webhook_url,
                webhook_secret, telegram_chat_id, now
            )
        else:
            await self.execute(
                """
                INSERT OR REPLACE INTO merchants (id, name, notification_type, webhook_url,
                                                  webhook_secret, telegram_chat_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
                """,
                merchant_id, name, notification_type, webhook_url,
                webhook_secret, telegram_chat_id, now.isoformat()
            )

        return await self.get_merchant(merchant_id)

    async def update_merchant_status(self, merchant_id: str, is_active: bool) -> None:
        """Update merchant active status."""
        await self.execute(
            "UPDATE merchants SET is_active = $1, updated_at = $2 WHERE id = $3",
            is_active, datetime.utcnow(), merchant_id
        )

    # -------------------------------------------------------------------------
    # Delivery Log Operations
    # -------------------------------------------------------------------------

    async def log_delivery(
        self,
        merchant_id: str,
        event_type: str,
        event_id: str,
        delivery_method: str,
        payload: str,
        success: bool,
        response_code: Optional[int] = None,
        response_body: Optional[str] = None,
        retry_count: int = 0,
        next_retry_at: Optional[datetime] = None
    ) -> int:
        """Log a delivery attempt."""
        now = datetime.utcnow()

        if self._is_postgres:
            result = await self.fetch_one(
                """
                INSERT INTO webhook_deliveries
                    (merchant_id, event_type, event_id, delivery_method, payload,
                     success, response_code, response_body, retry_count, next_retry_at,
                     delivered_at, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11)
                ON CONFLICT (event_id, merchant_id) DO UPDATE SET
                    success = EXCLUDED.success,
                    response_code = EXCLUDED.response_code,
                    response_body = EXCLUDED.response_body,
                    retry_count = EXCLUDED.retry_count,
                    next_retry_at = EXCLUDED.next_retry_at,
                    delivered_at = EXCLUDED.delivered_at
                RETURNING id
                """,
                merchant_id, event_type, event_id, delivery_method, payload,
                success, response_code, response_body, retry_count, next_retry_at, now
            )
            return result['id']
        else:
            # SQLite doesn't have RETURNING, so we insert and get last row id
            await self.execute(
                """
                INSERT OR REPLACE INTO webhook_deliveries
                    (merchant_id, event_type, event_id, delivery_method, payload,
                     success, response_code, response_body, retry_count, next_retry_at,
                     delivered_at, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11)
                """,
                merchant_id, event_type, event_id, delivery_method, payload,
                success, response_code, response_body, retry_count,
                next_retry_at.isoformat() if next_retry_at else None,
                now.isoformat()
            )
            cursor = await self._sqlite_conn.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            return row[0]

    async def get_pending_retries(self) -> List[Dict[str, Any]]:
        """Get deliveries pending retry."""
        now = datetime.utcnow()

        if self._is_postgres:
            return await self.fetch_all(
                """
                SELECT wd.*, m.webhook_url, m.webhook_secret, m.telegram_chat_id
                FROM webhook_deliveries wd
                JOIN merchants m ON wd.merchant_id = m.id
                WHERE wd.success = FALSE
                  AND wd.next_retry_at IS NOT NULL
                  AND wd.next_retry_at <= $1
                ORDER BY wd.next_retry_at
                """,
                now
            )
        else:
            return await self.fetch_all(
                """
                SELECT wd.*, m.webhook_url, m.webhook_secret, m.telegram_chat_id
                FROM webhook_deliveries wd
                JOIN merchants m ON wd.merchant_id = m.id
                WHERE wd.success = 0
                  AND wd.next_retry_at IS NOT NULL
                  AND wd.next_retry_at <= $1
                ORDER BY wd.next_retry_at
                """,
                now.isoformat()
            )

    async def mark_delivery_success(self, delivery_id: int) -> None:
        """Mark a delivery as successful."""
        await self.execute(
            """
            UPDATE webhook_deliveries
            SET success = TRUE, next_retry_at = NULL, delivered_at = $1
            WHERE id = $2
            """,
            datetime.utcnow(), delivery_id
        )

    async def update_delivery_retry(
        self,
        delivery_id: int,
        retry_count: int,
        next_retry_at: Optional[datetime],
        response_code: Optional[int] = None,
        response_body: Optional[str] = None
    ) -> None:
        """Update delivery for retry."""
        if self._is_postgres:
            await self.execute(
                """
                UPDATE webhook_deliveries
                SET retry_count = $1, next_retry_at = $2, response_code = $3,
                    response_body = $4, delivered_at = $5
                WHERE id = $6
                """,
                retry_count, next_retry_at, response_code, response_body,
                datetime.utcnow(), delivery_id
            )
        else:
            await self.execute(
                """
                UPDATE webhook_deliveries
                SET retry_count = $1, next_retry_at = $2, response_code = $3,
                    response_body = $4, delivered_at = $5
                WHERE id = $6
                """,
                retry_count,
                next_retry_at.isoformat() if next_retry_at else None,
                response_code, response_body,
                datetime.utcnow().isoformat(), delivery_id
            )

    # -------------------------------------------------------------------------
    # Block Tracking Operations
    # -------------------------------------------------------------------------

    async def get_last_processed_block(self) -> int:
        """Get the last processed block number."""
        result = await self.fetch_one(
            "SELECT block_number FROM processed_blocks WHERE id = 'last_block'"
        )
        return result['block_number'] if result else 0

    async def update_last_processed_block(self, block_number: int) -> None:
        """Update the last processed block number."""
        now = datetime.utcnow()

        if self._is_postgres:
            await self.execute(
                """
                INSERT INTO processed_blocks (id, block_number, updated_at)
                VALUES ('last_block', $1, $2)
                ON CONFLICT (id) DO UPDATE SET
                    block_number = EXCLUDED.block_number,
                    updated_at = EXCLUDED.updated_at
                """,
                block_number, now
            )
        else:
            await self.execute(
                """
                INSERT OR REPLACE INTO processed_blocks (id, block_number, updated_at)
                VALUES ('last_block', $1, $2)
                """,
                block_number, now.isoformat()
            )

    # -------------------------------------------------------------------------
    # Payment Event Operations
    # -------------------------------------------------------------------------

    async def save_payment_event(
        self,
        payment_id: str,
        merchant_id: str,
        customer_address: str,
        token_address: str,
        amount: str,
        transaction_hash: str,
        block_number: int,
        block_timestamp: datetime
    ) -> None:
        """Save a payment event."""
        now = datetime.utcnow()

        if self._is_postgres:
            await self.execute(
                """
                INSERT INTO payment_events
                    (id, merchant_id, customer_address, token_address, amount,
                     transaction_hash, block_number, block_timestamp, processed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO NOTHING
                """,
                payment_id, merchant_id, customer_address, token_address, amount,
                transaction_hash, block_number, block_timestamp, now
            )
        else:
            await self.execute(
                """
                INSERT OR IGNORE INTO payment_events
                    (id, merchant_id, customer_address, token_address, amount,
                     transaction_hash, block_number, block_timestamp, processed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                payment_id, merchant_id, customer_address, token_address, amount,
                transaction_hash, block_number, block_timestamp.isoformat(), now.isoformat()
            )

    async def mark_payment_notified(self, payment_id: str) -> None:
        """Mark a payment as notified."""
        await self.execute(
            "UPDATE payment_events SET notification_sent = TRUE WHERE id = $1",
            payment_id
        )

    async def check_event_processed(self, event_id: str, merchant_id: str) -> bool:
        """Check if an event has already been processed for a merchant."""
        result = await self.fetch_one(
            """
            SELECT id FROM webhook_deliveries
            WHERE event_id = $1 AND merchant_id = $2 AND success = TRUE
            """,
            event_id, merchant_id
        )
        return result is not None


# Global database instance
_db: Optional[Database] = None


async def get_db() -> Database:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
    return _db


async def close_db() -> None:
    """Close the global database connection."""
    global _db
    if _db is not None:
        await _db.disconnect()
        _db = None
