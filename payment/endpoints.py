from fastapi import FastAPI, Request, HTTPException, APIRouter
from yookassa.domain.notification import (
    WebhookNotificationEventType,
    WebhookNotificationFactory,
)
from yookassa.domain.common import SecurityHelper
from db.redis.client import payments
from bot.bot import success_payment_message, failure_payment_message
from logger_config import logger

app = FastAPI()

router = APIRouter(prefix="/infobot")


@router.post("/payment")
async def webhook(request: Request):
    logger.info("Payment webhook")
    ip = request.client.host
    if not SecurityHelper().is_ip_trusted(ip):
        logger.info("IP is not in trusted list")
        raise HTTPException(status_code=400)
    event_json = await request.json()
    try:
        logger.info(f"Event json: {event_json}")
        notification_object = WebhookNotificationFactory().create(event_json)
        response_object = notification_object.object
        
    
        payment_status = notification_object.event
        payment_id = get_id_by_status(response_object, payment_status)
        client_id = await payments.payments.get_key(payment_id) 
        
        logger.info(f"Payment {payment_id} status: {payment_status} for client {client_id}")

        if payment_status == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            result = await payments.confirm_payment(client_id, payment_id)
            logger.info(f"Payment {payment_id} confirmation status: {result} for client {client_id}")
            if result:
                logger.info(f"Send success payment message for client {client_id}")
                await success_payment_message(client_id)
            else:
                logger.info(f"Cancel payment for client {client_id}")
                raise HTTPException(status_code=500)
        else:
            result = await payments.cancel_payment(client_id, payment_id)
            logger.info(f"Payment {payment_id} cancelation status: {result} for client {client_id}")
            
            if result:
                logger.info(f"Cancel payment for client {client_id}")
                await failure_payment_message(client_id, payment_status)
            else:
                logger.info(f"Send failed cancel payment message for client {client_id} to YooKassa")
                raise HTTPException(status_code=500)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f'Webhook error: {e}', exc_info=True)
        raise HTTPException(status_code=400)


def get_id_by_status(event_object, status):
    if status in {
        WebhookNotificationEventType.PAYMENT_SUCCEEDED,
        WebhookNotificationEventType.PAYMENT_WAITING_FOR_CAPTURE,
        WebhookNotificationEventType.PAYMENT_CANCELED,
        WebhookNotificationEventType.DEAL_CLOSED,
        WebhookNotificationEventType.PAYOUT_SUCCEEDED,
        WebhookNotificationEventType.PAYOUT_CANCELED,
    }:
        return event_object.id
    elif status in {
        WebhookNotificationEventType.REFUND_SUCCEEDED
    }:
        return event_object.payment_id
    else:
        return None