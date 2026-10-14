import pytest
from fastapi.testclient import TestClient
from database import get_db
from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession
from sqlalchemy.orm import sessionmaker
from main import app
from models import Base,User,History,Site
from sqlalchemy import create_engine,delete
import httpx
import pytest_asyncio
from datetime import timedelta
from auth import create_token

client=TestClient(app)

engine=create_async_engine('sqlite+aiosqlite:///test_workerparser.db')
sync_engine=create_engine('sqlite:///test_workerparser.db')
Base.metadata.create_all(sync_engine)

TestSession=sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) #type:ignore

async def fetch(url, type, params={}):
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(base_url='http://127.0.0.1', transport=transport) as testclient:
        if type=='get':
            response=await testclient.get(url)
            return response.status_code
        elif type=='post':
            response=await testclient.post(url, data=params)
            return response.status_code

async def get_overdb():
    async with TestSession() as db: #type:ignore
        try:
            yield db
        finally:
            await db.close()

app.dependency_overrides[get_db]=get_overdb

@pytest_asyncio.fixture
async def db():
    async with TestSession() as connection: #type:ignore
        try:
            yield connection
        finally:
            await connection.close() #type:ignore

@pytest_asyncio.fixture(autouse=True)
async def clean_db(db):
    await db.execute(delete(User))
    await db.execute(delete(Site))
    await db.execute(delete(History))
    await db.commit()
    yield

async def test_registration():
    status=await fetch('/reg','post', {'name':'test', 'password':'123'})
    assert status==303

async def test_login():
    reg_status=await fetch('/reg','post', {'name':'test', 'password':'123'})
    login_status=await fetch('/login', 'post', {'name':'test', 'password':'123'})
    assert login_status==303

async def test_login_wrong():
    reg_status=await fetch('/reg','post', {'name':'test', 'password':'123'})
    login_status=await fetch('/login', 'post', {'name':'test', 'password':'1234'})
    assert login_status==401

async def test_add_card():
    reg_status=await fetch('/reg','post', {'name':'test', 'password':'123'})
    login_status=await fetch('/login', 'post', {'name':'test', 'password':'123'})
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(base_url='http://127.0.0.1', transport=transport) as testclient:
        response=await testclient.post('/products', json={'url':'https://store.steampowered.com/app/2416450/_/', 'title':'test', 'target_price':400}, cookies={'access_token':create_token(user='test', timedelta=timedelta(minutes=30))})
        assert response.status_code==404

async def test_reg_name_taken():
    reg_status=await fetch('/reg','post', {'name':'test', 'password':'123'})
    reg_status_2=await fetch('/reg','post', {'name':'test', 'password':'1234'})
    assert reg_status_2==401

async def test_history_show():
    reg_status=await fetch('/reg','post', {'name':'test', 'password':'123'})
    login_status=await fetch('/login', 'post', {'name':'test', 'password':'123'})
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(base_url='http://127.0.0.1', transport=transport) as testclient:
        response=await testclient.post('/history?period=7', json= {'page':1}, cookies={'access_token':create_token(user='test', timedelta=timedelta(minutes=30))})
        assert response.status_code==404
