"""Billing domain: plans, subscriptions, entitlements, coupons, attribution, payments.

Free beta is the default: every account holds at least a free subscription
and the backend (not the client) decides feature access. Payment providers
stay behind ``providers.PaymentProvider``; ``payment_provider = none`` today.
"""
