import hashlib
import hmac

import requests
from django.conf import settings

RAZORPAY_ORDERS_URL = 'https://api.razorpay.com/v1/orders'


def create_razorpay_order(amount_paise, receipt):
    response = requests.post(
        RAZORPAY_ORDERS_URL,
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        json={
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': receipt,
            'payment_capture': 1,
            'notes': {'receipt': receipt},
        },
        timeout=30,
    )
    if not response.ok:
        try:
            err = response.json().get('error', {})
            description = err.get('description') or err.get('reason') or response.text
        except Exception:
            description = response.text or 'Unknown Razorpay error'
        raise ValueError(description)
    return response.json()


def verify_razorpay_signature(order_id, payment_id, signature):
    message = f'{order_id}|{payment_id}'.encode('utf-8')
    # hmac.new is the correct Python 3 API
    mac = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode('utf-8'),
        message,
        hashlib.sha256,
    )
    expected = mac.hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError('Invalid payment signature')
