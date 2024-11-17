from yookassa import Payment, Configuration
from yookassa.domain.models.currency import Currency
from yookassa.domain.models.receipt import Receipt, ReceiptItem
from yookassa.domain.request.payment_request_builder import PaymentRequestBuilder
from dotenv import load_dotenv
from db.redis.client import payments
import os
import json

load_dotenv()

description = os.environ.get("PAYMENT_DESCRIPTION")
cost = float(os.environ.get("PAYMENT_COST"))


async def create_payment(client_id: str) -> str:
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

    builder = PaymentRequestBuilder()
    builder.set_amount({"value": cost, "currency": Currency.RUB}).set_capture(
        False
    ).set_description(description).set_receipt(receipt)

    request = builder.build()
    payment = json.loads(Payment.create(request).json())

    payment_id = payment.get("id")
    confirmation_url = payment.get("confirmation", {}).get("confirmation_url")

    if confirmation_url:
        return await payments.create_payment(client_id, payment_id, confirmation_url)


def configure_payment():
    account_id = os.environ.get("PAYMENT_ACCOUNT_ID")
    secret_key = float(os.environ.get("PAYMENT_SECRET_KEY"))
    Configuration.configure(account_id, secret_key)
