from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                choices=[('cod', 'Cash on Delivery'), ('razorpay', 'Razorpay')],
                default='cod',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='razorpay_order_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='order',
            name='razorpay_payment_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
