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
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def verify_razorpay_signature(order_id, payment_id, signature):
    message = f'{order_id}|{payment_id}'.encode('utf-8')
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode('utf-8'),
        message,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError('Invalid payment signature')
