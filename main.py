from fastapi import FastAPI
from models import Base
import os
from sqlalchemy import create_engine
from tasks import router
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_methods=['POST','DELETE','GET'],
    allow_origins=['http://127.0.0.1:8000', 'https://steamparser.onrender.com'],
    allow_headers=['*'],
)

url=os.getenv('DATABASE_URL', 'sqlite:///workerparser.db')
if '+asyncpg' in url:
    url=url.replace('+asyncpg','')
engine=create_engine(url)
Base.metadata.create_all(engine)

app.include_router(router)
