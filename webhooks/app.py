from fastapi import FastAPI
from .yookassa import router as yookassa_router
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()
host = os.environ.get('HOST')
port = int(os.environ.get('PORT'))
dev = bool(os.environ.get('DEV'))


app = FastAPI()
app.include_router(yookassa_router)

async def start_app():
    uvicorn.run('webhooks.app:app', host=host, port=port, reload=dev)