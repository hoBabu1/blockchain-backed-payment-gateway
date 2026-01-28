"""API module for Payment Gateway Notifications."""

from .merchant_api import create_app, MerchantAPI

__all__ = ['create_app', 'MerchantAPI']
