from yookassa import Payment, Configuration
from yookassa.domain.common import ConfirmationType
from yookassa.domain.models.currency import Currency
from yookassa.domain.models.receipt import Receipt, ReceiptItem
from yookassa.domain.request.payment_request_builder import PaymentRequestBuilder
from dotenv import load_dotenv
from config import env_float, env_str
from db.redis.client import payments
from logger_config import logger
import json

load_dotenv()

description = env_str("PAYMENT_DESCRIPTION", "")
receipt_email = env_str("PAYMENT_EMAIL")
receipt_phone = env_str("PAYMENT_PHONE")
webhook_url = env_str("PAYMENT_WEBHOOK_URL")
cost = env_float("PAYMENT_COST", required=True)


async def create_payment(client_id: str, target_user: str = None) -> str:
    try:
        request = build_payment_request()
        payment = json.loads(Payment.create(request).json())
    except Exception as e:
        logger.error(f"YooKassa payment creation failed: {e}", exc_info=True)
        return None

    payment_id = payment.get("id")
    confirmation_url = payment.get("confirmation", {}).get("confirmation_url")

    if not confirmation_url:
        logger.error(f"YooKassa response has no confirmation url: {payment}")
        return None

    try:
        return await payments.create_payment(
            client_id, payment_id, confirmation_url, target_user=target_user
        )
    except Exception as e:
        logger.error(f"Payment {payment_id} saving failed: {e}", exc_info=True)
        return None


def build_payment_request():
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

    # Сеттеры ЮKassa валидируют формат и падают на пустом значении, поэтому
    # незаданные контакты не выставляются вовсе.
    if receipt_email:
        receipt.email = receipt_email
    if receipt_phone:
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

    return builder.build()


def configure_payment():
    account_id = env_str("PAYMENT_ACCOUNT_ID", required=True)
    secret_key = env_str("PAYMENT_SECRET_KEY", required=True)
    Configuration.configure(account_id, secret_key)
    Configuration.configure_user_agent()
