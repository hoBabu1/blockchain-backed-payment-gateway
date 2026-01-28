"""
Merchant Registration API.

Provides REST endpoints for merchant registration and management.
"""

import logging
import re
from typing import Optional

from aiohttp import web

from config import config
from database.db import Database
from models.merchant import Merchant, NotificationType
from services.webhook_service import WebhookService
from services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

# Ethereum address validation regex
ETH_ADDRESS_REGEX = re.compile(r'^0x[a-fA-F0-9]{40}$')


class MerchantAPI:
    """
    REST API for merchant management.

    Endpoints:
    - POST /api/merchant/register - Register a new merchant
    - GET /api/merchant/{id} - Get merchant details
    - PUT /api/merchant/{id} - Update merchant settings
    - DELETE /api/merchant/{id} - Deactivate merchant
    - POST /api/merchant/{id}/test - Send test notification
    - GET /api/health - Health check
    - GET /api/stats - Service statistics
    """

    def __init__(
        self,
        db: Database,
        webhook_service: Optional[WebhookService] = None,
        telegram_service: Optional[TelegramService] = None
    ):
        """
        Initialize the API.

        Args:
            db: Database instance
            webhook_service: Optional webhook service for verification
            telegram_service: Optional Telegram service for verification
        """
        self.db = db
        self.webhook_service = webhook_service
        self.telegram_service = telegram_service

    def setup_routes(self, app: web.Application) -> None:
        """
        Set up API routes.

        Args:
            app: aiohttp web application
        """
        app.router.add_post('/api/merchant/register', self.register_merchant)
        app.router.add_get('/api/merchant/{merchant_id}', self.get_merchant)
        app.router.add_put('/api/merchant/{merchant_id}', self.update_merchant)
        app.router.add_delete('/api/merchant/{merchant_id}', self.deactivate_merchant)
        app.router.add_post('/api/merchant/{merchant_id}/test', self.test_notification)
        app.router.add_get('/api/health', self.health_check)
        app.router.add_get('/api/stats', self.get_stats)
        app.router.add_get('/api/webhook/verify-code/{language}', self.get_verification_code)

    async def register_merchant(self, request: web.Request) -> web.Response:
        """
        Register a new merchant.

        Request body:
        {
            "merchant_id": "0x123...",
            "notification_type": "webhook" | "telegram",
            "name": "My Shop" (optional),
            "webhook_url": "https://..." (required for webhook),
            "telegram_chat_id": "123456789" (required for telegram)
        }
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"error": "Invalid JSON body"},
                status=400
            )

        # Validate required fields
        merchant_id = data.get('merchant_id')
        notification_type = data.get('notification_type')

        if not merchant_id:
            return web.json_response(
                {"error": "merchant_id is required"},
                status=400
            )

        if not ETH_ADDRESS_REGEX.match(merchant_id):
            return web.json_response(
                {"error": "Invalid Ethereum address format"},
                status=400
            )

        if notification_type not in ['webhook', 'telegram']:
            return web.json_response(
                {"error": "notification_type must be 'webhook' or 'telegram'"},
                status=400
            )

        # Validate type-specific fields
        if notification_type == 'webhook':
            webhook_url = data.get('webhook_url')
            if not webhook_url:
                return web.json_response(
                    {"error": "webhook_url is required for webhook notifications"},
                    status=400
                )
            if not webhook_url.startswith(('http://', 'https://')):
                return web.json_response(
                    {"error": "webhook_url must be a valid HTTP(S) URL"},
                    status=400
                )

            # Optionally verify webhook URL is reachable
            if self.webhook_service:
                is_valid, msg = await self.webhook_service.verify_webhook_url(webhook_url)
                if not is_valid:
                    logger.warning(f"Webhook URL verification failed: {msg}")
                    # Don't fail registration, just warn

            # Create merchant with webhook config
            merchant = Merchant.create_webhook_merchant(
                merchant_id=merchant_id,
                webhook_url=webhook_url,
                name=data.get('name')
            )

        else:  # telegram
            telegram_chat_id = data.get('telegram_chat_id')
            if not telegram_chat_id:
                return web.json_response(
                    {"error": "telegram_chat_id is required for Telegram notifications"},
                    status=400
                )

            # Create merchant with Telegram config
            merchant = Merchant.create_telegram_merchant(
                merchant_id=merchant_id,
                telegram_chat_id=telegram_chat_id,
                name=data.get('name')
            )

        # Save to database
        try:
            await self.db.create_merchant(
                merchant_id=merchant.id,
                notification_type=merchant.notification_type.value,
                name=merchant.name,
                webhook_url=merchant.webhook_url,
                webhook_secret=merchant.webhook_secret,
                telegram_chat_id=merchant.telegram_chat_id
            )
        except Exception as e:
            logger.error(f"Error creating merchant: {e}")
            return web.json_response(
                {"error": "Failed to register merchant"},
                status=500
            )

        logger.info(f"Registered merchant {merchant.short_id()} with {notification_type} notifications")

        # Return merchant data (with secret for webhook)
        response_data = {
            "success": True,
            "merchant": merchant.to_dict()
        }

        # Include helpful info based on notification type
        if notification_type == 'webhook':
            response_data["message"] = (
                "Merchant registered successfully. "
                "Save your webhook_secret - you'll need it to verify webhook signatures."
            )
        else:
            response_data["message"] = (
                "Merchant registered successfully. "
                "Make sure you've started a conversation with the bot to receive notifications."
            )

        return web.json_response(response_data, status=201)

    async def get_merchant(self, request: web.Request) -> web.Response:
        """Get merchant details."""
        merchant_id = request.match_info['merchant_id']

        if not ETH_ADDRESS_REGEX.match(merchant_id):
            return web.json_response(
                {"error": "Invalid merchant ID format"},
                status=400
            )

        merchant_data = await self.db.get_merchant(merchant_id.lower())

        if not merchant_data:
            return web.json_response(
                {"error": "Merchant not found"},
                status=404
            )

        merchant = Merchant.from_dict(merchant_data)

        return web.json_response({
            "merchant": merchant.to_public_dict()
        })

    async def update_merchant(self, request: web.Request) -> web.Response:
        """
        Update merchant settings.

        Allows updating:
        - name
        - notification_type (switches delivery method)
        - webhook_url (for webhook type)
        - telegram_chat_id (for telegram type)
        - is_active
        """
        merchant_id = request.match_info['merchant_id']

        if not ETH_ADDRESS_REGEX.match(merchant_id):
            return web.json_response(
                {"error": "Invalid merchant ID format"},
                status=400
            )

        existing = await self.db.get_merchant(merchant_id.lower())
        if not existing:
            return web.json_response(
                {"error": "Merchant not found"},
                status=404
            )

        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"error": "Invalid JSON body"},
                status=400
            )

        # Build update values
        notification_type = data.get('notification_type', existing['notification_type'])
        name = data.get('name', existing.get('name'))
        webhook_url = data.get('webhook_url', existing.get('webhook_url'))
        webhook_secret = existing.get('webhook_secret')
        telegram_chat_id = data.get('telegram_chat_id', existing.get('telegram_chat_id'))

        # If switching to webhook, generate new secret
        if notification_type == 'webhook' and existing['notification_type'] != 'webhook':
            webhook_secret = Merchant.generate_secret()

        # Validate based on new notification type
        if notification_type == 'webhook' and not webhook_url:
            return web.json_response(
                {"error": "webhook_url is required for webhook notifications"},
                status=400
            )
        if notification_type == 'telegram' and not telegram_chat_id:
            return web.json_response(
                {"error": "telegram_chat_id is required for Telegram notifications"},
                status=400
            )

        # Update in database
        await self.db.create_merchant(
            merchant_id=merchant_id.lower(),
            notification_type=notification_type,
            name=name,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
            telegram_chat_id=telegram_chat_id
        )

        # Handle is_active separately
        if 'is_active' in data:
            await self.db.update_merchant_status(
                merchant_id.lower(),
                bool(data['is_active'])
            )

        # Fetch updated merchant
        updated = await self.db.get_merchant(merchant_id.lower())
        merchant = Merchant.from_dict(updated)

        logger.info(f"Updated merchant {merchant.short_id()}")

        return web.json_response({
            "success": True,
            "merchant": merchant.to_public_dict()
        })

    async def deactivate_merchant(self, request: web.Request) -> web.Response:
        """Deactivate a merchant (soft delete)."""
        merchant_id = request.match_info['merchant_id']

        if not ETH_ADDRESS_REGEX.match(merchant_id):
            return web.json_response(
                {"error": "Invalid merchant ID format"},
                status=400
            )

        existing = await self.db.get_merchant(merchant_id.lower())
        if not existing:
            return web.json_response(
                {"error": "Merchant not found"},
                status=404
            )

        await self.db.update_merchant_status(merchant_id.lower(), False)

        logger.info(f"Deactivated merchant {merchant_id[:10]}...")

        return web.json_response({
            "success": True,
            "message": "Merchant deactivated successfully"
        })

    async def test_notification(self, request: web.Request) -> web.Response:
        """Send a test notification to verify setup."""
        merchant_id = request.match_info['merchant_id']

        if not ETH_ADDRESS_REGEX.match(merchant_id):
            return web.json_response(
                {"error": "Invalid merchant ID format"},
                status=400
            )

        merchant_data = await self.db.get_merchant(merchant_id.lower())
        if not merchant_data:
            return web.json_response(
                {"error": "Merchant not found"},
                status=404
            )

        merchant = Merchant.from_dict(merchant_data)

        if merchant.is_telegram() and self.telegram_service:
            success, message = await self.telegram_service.send_test_message(
                merchant.telegram_chat_id
            )
            return web.json_response({
                "success": success,
                "message": message,
                "method": "telegram"
            })

        elif merchant.is_webhook() and self.webhook_service:
            is_reachable, message = await self.webhook_service.verify_webhook_url(
                merchant.webhook_url
            )
            return web.json_response({
                "success": is_reachable,
                "message": message,
                "method": "webhook"
            })

        return web.json_response({
            "error": "Notification service not available"
        }, status=503)

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "service": config.service.name
        })

    async def get_stats(self, request: web.Request) -> web.Response:
        """Get service statistics."""
        merchants = await self.db.get_active_merchants()

        webhook_count = sum(
            1 for m in merchants
            if m.get('notification_type') == 'webhook'
        )
        telegram_count = sum(
            1 for m in merchants
            if m.get('notification_type') == 'telegram'
        )

        return web.json_response({
            "total_merchants": len(merchants),
            "webhook_merchants": webhook_count,
            "telegram_merchants": telegram_count
        })

    async def get_verification_code(self, request: web.Request) -> web.Response:
        """Get webhook signature verification code for a language."""
        from services.webhook_service import generate_signature_verification_code

        language = request.match_info['language']
        code = generate_signature_verification_code(language)

        return web.Response(
            text=code,
            content_type='text/plain'
        )


def create_app(
    db: Database,
    webhook_service: Optional[WebhookService] = None,
    telegram_service: Optional[TelegramService] = None
) -> web.Application:
    """
    Create and configure the aiohttp web application.

    Args:
        db: Database instance
        webhook_service: Optional webhook service
        telegram_service: Optional Telegram service

    Returns:
        Configured aiohttp Application
    """
    app = web.Application()

    # Create API handler
    api = MerchantAPI(
        db=db,
        webhook_service=webhook_service,
        telegram_service=telegram_service
    )

    # Setup routes
    api.setup_routes(app)

    # Add CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            response = await handler(request)

        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    app.middlewares.append(cors_middleware)

    # Error handling middleware
    @web.middleware
    async def error_middleware(request, handler):
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unhandled error: {e}", exc_info=True)
            return web.json_response(
                {"error": "Internal server error"},
                status=500
            )

    app.middlewares.append(error_middleware)

    return app
