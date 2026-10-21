import aio_pika as pika
import json
import httpx
from bs4 import BeautifulSoup
import asyncio
from fastapi import FastAPI
import os
import uuid
import logger
import redis.asyncio as redis

#i[0] -id  i[1] - url i[2] - user_id

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

app=FastAPI()

if os.getenv('REDIS_URL'):
    r=redis.from_url(os.getenv('REDIS_URL',''),decode_responses=True)
else: r=redis.Redis(decode_responses=True)

async def main():
    connection=await pika.connect_robust(os.getenv('RABBITMQ_URL',None))
    channel=await connection.channel()
    main_queue=await channel.declare_queue('sites')
    dlx_queue=await channel.declare_queue('dlx',durable=True)
    queue=await channel.declare_queue('retry', durable=True, arguments={'x-message-ttl': 30000, 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': 'sites'})

    async def callback(message:pika.IncomingMessage):
        dlx=[]
        all_requests=[]
        async with message.process():
            data=json.loads(message.body.decode())
            async with httpx.AsyncClient() as client:
                for site in data:
                    count=await r.get(f'site_id:{site[0]}')
                    if not(count):
                        await r.set(f'site_id:{site[0]}', 1)
                        count=1
                    count=int(count)
                    if not(site[1].startswith('https://store.steampowered.com')):
                        dlx.append(site)
                        continue
                    request=await client.get(site[1])
                    if count+1>3: #type:ignore
                        dlx.append(site)
                    await r.set(f'site_id:{site[0]}',count+1)
                    if site not in dlx: all_requests.append(site) 
            if all_requests:
                await channel.default_exchange.publish(pika.Message(json.dumps(all_requests).encode()), 'sites')
            if dlx:
                await channel.default_exchange.publish(pika.Message(json.dumps(dlx).encode()), 'dlx')

    await queue.consume(callback) #type:ignore
    try:
        await asyncio.Future()
    except KeyboardInterrupt: return

@app.on_event('startup')
async def startup():
    logger.logger.info(f'Started Retry RabbitMQ worker')
    spawn(main())

@app.get('/')
async def root():
    return {'status':'ok'}
