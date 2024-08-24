from dotenv import load_dotenv
import os
from redis import asyncio as aioredis

load_dotenv()

host = os.environ.get('DB_HOST')
port = int(os.environ.get('DB_PORT'))
user = os.environ.get('DB_USER')
password = os.environ.get('DB_PASSWORD')

connection_string = f'redis://{host}:{port}'

class RedisDatabase:
    def __init__(self, db_number):
        self.redis = aioredis.from_url(
            connection_string, username=user, password=password, db=db_number,
            decode_responses=True
        )

    async def set_key(self, key, value):
        try:
            await self.redis.set(key, value)
            return True
        except Exception as e:
            print(e)
            return False

    async def get_key(self, key):
        try:
            return await self.redis.get(key)
        except Exception as e:
            print(e)

    async def close(self):
        await self.redis.close()

class UserDatabase(RedisDatabase):
    def __init__(self):
        super().__init__(db_number=1)

    async def add_user(self, client_id: str) -> bool:
        return await self.set_key(client_id, client_id)

    async def check_paid(self, client_id: str) -> str:
        return await self.get_key(client_id)

class PaymentDatabase(RedisDatabase):
    def __init__(self):
        super().__init__(db_number=2)

    async def create_payment(self, payment_id: str, client_id: str) -> bool:
        return await self.set_key(payment_id, client_id)

    async def close_payment(self, payment_id: str) -> str:
        return await self.get_key(payment_id)


payments = PaymentDatabase()
users = UserDatabase()

async def initialize_db():
    privileged_users = os.environ.get('PAYMENT_PRIVILEGED_USERS').split(',')
    for user in privileged_users:
        await users.add_user(user)

async def close_connections():
    await payments.close()
    await users.close()
