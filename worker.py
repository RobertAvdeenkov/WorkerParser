import httpx
from bs4 import BeautifulSoup
import aio_pika as pika
import asyncio
import json
from database import SessionLocal
from sqlalchemy import text
from datetime import datetime
from fastapi import FastAPI
import os
import logger

app=FastAPI()

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.wildberries.ru/",
}

async def main():
    RABBITMQ_URL=os.getenv('RABBITMQ_URL', None)
    connection= await pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel=await connection.channel()
        queue=await channel.declare_queue('sites')
        exchange=await channel.declare_queue('retry', durable=True,  arguments={'x-message-ttl': 30000, 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': 'sites'})
        await channel.declare_queue('dlx', durable=True)

        async def callback(message:pika.IncomingMessage):
            async with message.process():
                data=json.loads(message.body.decode())
                result=[]
                retry=[]
                async with httpx.AsyncClient() as client:
                    for i in data:
                        response=await client.get(i[1], headers=headers)
                        if response.status_code==200:
                            soup=BeautifulSoup(response.content, 'html.parser')
                            if i[1].startswith('https://store.steampowered.com'):
                                pricediv=soup.find(class_='discount_final_price')
                                if pricediv:
                                    pricediv=pricediv.get_text(strip=True).strip('руб.').strip('€').strip('$')
                                else:
                                    pricediv=soup.find(class_='game_purchase_price price')
                                    if pricediv:
                                        pricediv=pricediv.get('data-price-final')
                                pricediv=str(pricediv).replace(',','.')[:-2:]
                                result.append((i[0], response.status_code, round(float(pricediv)) if pricediv!='No' else 0, i[2])) #type:ignore
                            else:
                                retry.append((i[0],i[1],i[2]))
                        else:
                            retry.append((i[0],i[1],i[2]))
                async with SessionLocal() as db: #type:ignore
                    if result:
                        await db.execute(
                            text('UPDATE sites SET last_seen = NOW(), status_code = :code, last_price = :lp WHERE id = :id'),
                            [{'code': int(i[1]), 'id': int(i[0]), 'lp':int(i[2])} for i in result]
                        )
                        await db.execute(text('INSERT INTO history (price, created_at, user_id, sites_id) VALUES (:price, :createdat, :ui, :si)'),
                                        [{'price':int(j[2]), 'createdat':datetime.now(), 'ui':int(j[3]), 'si':int(j[0])} for j in result])
                        await db.commit()
                await channel.default_exchange.publish(pika.Message(json.dumps(retry).encode()), 'retry')
        await queue.consume(callback) #type:ignore
        logger.logger.info('Started RabbitMQ Worker')
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            return

@app.on_event('startup')
async def worker():
    spawn(main())

@app.get('/')
async def root():
    return {'status':'ok'}