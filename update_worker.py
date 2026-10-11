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
from tasks import update_worker

update=FastAPI()


@update.on_event('startup')
async def worker():
    print('started')
    asyncio.create_task(update_worker())

@update.get('/')
async def root():
    return {'status':'ok'}
    
uvicorn.run(update, host='0.0.0.0', port=int(os.getenv('PORT', 10000)))