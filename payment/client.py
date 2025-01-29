from yookassa import Payment, Configuration
from yookassa.domain.common import ConfirmationType
from yookassa.domain.models.currency import Currency
from yookassa.domain.models.receipt import Receipt, ReceiptItem
from yookassa.domain.request.payment_request_builder import PaymentRequestBuilder
from dotenv import load_dotenv
from db.redis.client import payments
import os
import json

load_dotenv()

description = os.environ.get("PAYMENT_DESCRIPTION")
receipt_email = os.environ.get("PAYMENT_EMAIL")
receipt_phone = os.environ.get("PAYMENT_PHONE")
webhook_url = os.environ.get("PAYMENT_WEBHOOK_URL")
cost = float(os.environ.get("PAYMENT_COST"))


async def create_payment(client_id: str, target_user: str = None) -> str:
    receipt = Receipt()
    receipt.tax_system_code = 1
    receipt.items = [
        ReceiptItem(
            {
                "description": description,
                "quantity": 1.0,
                "amount": {"value": cost, "currency": Currency.RUB},
                "vat_code": 2,
            }
        ),
    ]
    receipt.email = receipt_email
    receipt.phone = receipt_phone

    builder = PaymentRequestBuilder()
    builder.set_amount({"value": cost, "currency": Currency.RUB}).set_capture(
        True
    ).set_description(description).set_receipt(receipt).set_confirmation(
        {
            "type": ConfirmationType.REDIRECT,
            "return_url": webhook_url,
        }
    )

    request = builder.build()
    payment = json.loads(Payment.create(request).json())

    payment_id = payment.get("id")
    confirmation_url = payment.get("confirmation", {}).get("confirmation_url")

    if confirmation_url:
        return await payments.create_payment(client_id, payment_id, confirmation_url, target_user=target_user)


def configure_payment():
    account_id = os.environ.get("PAYMENT_ACCOUNT_ID")
    secret_key = os.environ.get("PAYMENT_SECRET_KEY")
    Configuration.configure(account_id, secret_key)
    Configuration.configure_user_agent()
