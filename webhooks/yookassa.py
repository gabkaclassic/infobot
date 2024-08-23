from fastapi import APIRouter, FastAPI, Request

app = FastAPI()

router = APIRouter(prefix='/infobot')


@router.post('/yoomoney')
async def webhook(request: Request):
    return ''