from fastapi import FastAPI
from models import Base
import os
from sqlalchemy import create_engine
from tasks import router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logger
from database import engine

logger.logger.info('App started')

app=FastAPI()
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

app.add_middleware(
    CORSMiddleware,
    allow_methods=['POST','DELETE','GET'],
    allow_origins=['http://127.0.0.1:8000', 'https://steamparser.onrender.com'],
    allow_headers=['*'],
)

@app.on_event('startup')
async def startup():
    url=os.getenv('DATABASE_URL','sqlite:///workerparser.db')
    engine=create_engine(url.replace('+asyncpg',''))
    Base.metadata.create_all(bind=engine)

app.include_router(router)
