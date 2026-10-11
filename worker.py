import httpx
from bs4 import BeautifulSoup
import aio_pika as pika
import asyncio
import json
from database import SessionLocal
from sqlalchemy import text
from datetime import datetime
from fastapi import FastAPI
import uvicorn
import os

app=FastAPI()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.wildberries.ru/",
}

async def callback(message:pika.IncomingMessage):
    global counter
    async with message.process():
        data=json.loads(message.body.decode())
        result=[]
        async with httpx.AsyncClient() as client:
            for i in data:
                response=await client.get(i[1], headers=headers)
                try:
                    print('started')
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
                        print(pricediv, i[1])
                finally:
                    result.append((i[0], response.status_code, round(float(pricediv)) if pricediv!='No' else 0, i[2])) #type:ignore
        async with SessionLocal() as db: #type:ignore
            print(result)
            await db.execute(
                text('UPDATE sites SET last_seen = NOW(), status_code = :code, last_price = :lp WHERE id = :id'),
                [{'code': i[1], 'id': i[0], 'lp':i[2]} for i in result]
            )
            await db.execute(text('INSERT INTO history (price, created_at, user_id, sites_id) VALUES (:price, :createdat, :ui, :si)'),
                            [{'price':j[2], 'createdat':datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'ui':j[3], 'si':j[0]} for j in result])
            await db.commit()


async def main():
    connection= await pika.connect_robust(os.getenv('RABBITMQ_URL', ''))
    async with connection:
        channel=await connection.channel()
        queue=await channel.declare_queue('sites')

        await queue.consume(callback) #type:ignore
        print('started')
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            return

@app.on_event('startup')
async def worker():
    asyncio.create_task(main())

@app.get('/')
async def root():
    return {'status':'ok'}