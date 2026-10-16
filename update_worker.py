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
import logger

update=FastAPI()

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

@update.on_event('startup')
async def worker():
    logger.logger.info('Started Update Worker')
    spawn(update_worker())

@update.get('/')
async def root():
    return {'status':'ok'}