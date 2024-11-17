from fastapi import FastAPI
from .endpoints import router as yookassa_router
import uvicorn
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from db.redis.client import initialize_db, close_connections, check_db
from payment.client import configure_payment

load_dotenv()
host = os.environ.get("HOST")
port = int(os.environ.get("PORT"))
dev = bool(os.environ.get("DEV"))


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
    uvicorn.run("payment.app:app", host=host, port=port, reload=dev)
