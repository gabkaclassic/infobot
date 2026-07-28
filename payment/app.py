from fastapi import FastAPI
from .endpoints import router as yookassa_router
import uvicorn
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from config import env_bool, env_int, env_str
from db.redis.client import initialize_db, close_connections, check_db
from payment.client import configure_payment

load_dotenv()
host = env_str("HOST", "0.0.0.0")
port = env_int("PORT", 8000)
dev = env_bool("DEV", False)
# Приложение стоит за реверс-прокси, поэтому реальный IP ЮKassa приходит в
# X-Forwarded-For. uvicorn подставит его в request.client только если сам прокси
# перечислен здесь.
forwarded_allow_ips = env_str("FORWARDED_ALLOW_IPS", "127.0.0.1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_payment()
    await check_db()
    await initialize_db()
    yield
    await close_connections()


app = FastAPI(lifespan=lifespan)
app.include_router(yookassa_router)


async def start_app():
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        reload=dev,
        proxy_headers=True,
        forwarded_allow_ips=forwarded_allow_ips,
    )
    server = uvicorn.Server(config)
    await server.serve()
