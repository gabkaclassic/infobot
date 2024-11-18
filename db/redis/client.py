from dotenv import load_dotenv
import os
from redis import asyncio as aioredis
import json, asyncio

load_dotenv()

host = os.environ.get("DB_HOST")
port = int(os.environ.get("DB_PORT"))
user = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")

connection_string = f"redis://{host}:{port}"


class RedisDatabase:
    def __init__(self, db_number):
        self.redis = aioredis.from_url(
            connection_string,
            username=user,
            password=password,
            db=db_number,
            decode_responses=True,
        )

    async def set_key(self, key, value):
        try:
            await self.redis.set(key, json.dumps(value))
            return True
        except Exception as e:
            print(e)
            return False

    async def get_key(self, key):
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else dict()
        except Exception as e:
            print(e)

    async def delete(self, key):
        try:
            return await self.redis.delete(key)
        except Exception as e:
            print(e)

    async def close(self):
        await self.redis.close()


class UserDatabase(RedisDatabase):
    def __init__(self):
        super().__init__(db_number=1)

    async def add_user(self, client_id: str, confirmation_url: str) -> bool:
        if client_id:
            return await self.set_key(
                client_id,
                {
                    "confirmation_url": confirmation_url,
                    "paid": False,
                },
            )
        return False

    async def get_payment_info(self, client_id: str) -> bool:
        return await self.get_key(client_id)

    async def confirm_payment(self, client_id: str) -> bool:
        info = await self.get_key(client_id)
        info["paid"] = True
        del info["confirmation_url"]
        return await self.set_key(client_id, info)

    async def cancel_payment(self, client_id: str) -> bool:
        info = await self.get_key(client_id)
        info["paid"] = False
        del info["confirmation_url"]
        return await self.set_key(client_id, info)


class PaymentDatabase(RedisDatabase):
    def __init__(self):
        super().__init__(db_number=2)

    async def create_payment(self, payment_id: str, client_id: str) -> bool:
        return await self.set_key(payment_id, client_id)

    async def close_payment(self, payment_id: str) -> str:
        client_id = await self.get_key(payment_id)
        await self.delete(payment_id)
        return client_id


class PaymentManager:

    def __init__(self):
        self.payments = PaymentDatabase()
        self.users = UserDatabase()

    async def create_payment(
        self, client_id: str, payment_id: str, confirmation_url: str
    ) -> str:
        async with self.payments.redis.client.pipeline(
            transaction=True
        ) as pipe_payments:
            pipe_payments.set(payment_id, client_id)

            async with self.users.redis.client.pipeline(transaction=True) as pipe_users:
                pipe_users.set(
                    client_id,
                    json.dumps({"confirmation_url": confirmation_url, "paid": False}),
                )

                results_payments, results_users = await asyncio.gather(
                    pipe_payments.execute(), pipe_users.execute()
                )

                if all(results_payments) and all(results_users):
                    return confirmation_url
                else:
                    await self.users.cancel_payment(client_id)
                    await self.payments.close_payment(payment_id)

    async def confirm_payment(self, client_id: str, payment_id: str) -> bool:
        async with self.users.redis.client.pipeline(transaction=True) as pipe_users:
            pipe_users.set(client_id, json.dumps({"paid": True}))

            async with self.payments.redis.client.pipeline(
                transaction=True
            ) as pipe_payments:
                pipe_payments.delete(payment_id)

                results_users, results_payments = await asyncio.gather(
                    pipe_users.execute(), pipe_payments.execute()
                )

                return all(results_users) and all(results_payments)

    async def cancel_payment(self, client_id: str, payment_id: str) -> bool:
        async with self.users.redis.client.pipeline(transaction=True) as pipe_users:
            pipe_users.set(client_id, json.dumps({"paid": False}))

            async with self.payments.redis.client.pipeline(
                transaction=True
            ) as pipe_payments:
                pipe_payments.delete(payment_id)

                results_users, results_payments = await asyncio.gather(
                    pipe_users.execute(), pipe_payments.execute()
                )

                return all(results_users) and all(results_payments)


payments = PaymentManager()


async def check_db():
    payments_ping = await payments.payments.redis.ping()
    assert payments_ping, "Payments ping failed"
    users_ping = await payments.users.redis.ping()
    assert users_ping, "Users ping failed"


async def initialize_db():
    privileged_users = os.environ.get("PAYMENT_PRIVILEGED_USERS").split(",")
    for user in privileged_users:
        await payments.users.add_user(user, "")
        await payments.users.confirm_payment(user)


async def close_connections():
    await payments.payments.close()
    await payments.users.close()
