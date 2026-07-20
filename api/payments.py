from django.conf import settings


def get_razorpay_client():
    import razorpay
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_razorpay_order(amount_paise, receipt):
    client = get_razorpay_client()
    return client.order.create({
        'amount': amount_paise,
        'currency': 'INR',
        'receipt': receipt,
        'payment_capture': 1,
    })


def verify_razorpay_signature(order_id, payment_id, signature):
    client = get_razorpay_client()
    client.utility.verify_payment_signature({
        'razorpay_order_id': order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature,
    })
