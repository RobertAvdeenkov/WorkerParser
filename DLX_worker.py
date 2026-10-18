import aio_pika as pika
import json
import asyncio
from database import SessionLocal
from sqlalchemy import text
import os
from fastapi import FastAPI
import logger

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

app=FastAPI()

async def main():
    connection= await pika.connect_robust(os.getenv('RABBITMQ_URL',None))
    channel=await connection.channel()
    retry_queue= await channel.declare_queue('retry', durable=True, arguments={'x-message-ttl': 30000, 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': 'sites'})
    queue=await channel.declare_queue('dlx', durable=True)

    async def callback(message:pika.IncomingMessage):
        async with message.process():
            data=json.loads(message.body.decode())
            async with SessionLocal() as db: #type:ignore
                await db.execute(text('''
                UPDATE sites SET result=\'FAILED\' where id= :id_site
                '''), [{'id_site':i[0]} for i in data])
                await db.commit()

    await queue.consume(callback) #type:ignore
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        return

@app.on_event('startup')
async def startup():
    logger.logger.info('Started DLX RabbitMQ worker')
    spawn(main())

@app.get('/')
async def root():
    return {'status':'ok'}
