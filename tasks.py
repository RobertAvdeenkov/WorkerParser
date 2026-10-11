from fastapi import APIRouter, Depends,Body, Form,Cookie,HTTPException,Query
from fastapi.responses import RedirectResponse,FileResponse,JSONResponse
from database import get_db,SessionLocal
from auth import create_token,get_by_token
from models import User,Site,History
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,text,desc
from datetime import timedelta,datetime
import redis.asyncio as redis
import json
from sqlalchemy.orm import selectinload
import aio_pika as pika
import asyncio
import os

router=APIRouter()
r=redis.from_url(os.getenv('REDIS_URL',''))

async def update_worker():
    try:
        connection= await pika.connect_robust(os.getenv('RABBITMQ_URL', ''))
        channel= await connection.channel()
        queue= await channel.declare_queue('sites')
        async with channel:
            async with SessionLocal() as db: #type:ignore
                while True:
                    print('new requsts')
                    result=await db.execute(text('''
                    select id,url,user_id from sites
                    where last_seen<=NOW() - INTERVAL \'1 minute\'
                    '''))
                    sites=result.all()
                    all_sites=[]
                    for i in sites:
                        all_sites.append((str(i[0]),str(i[1]),str(i[2])))
                    print(all_sites)
                    if all_sites:
                        await channel.default_exchange.publish(message=pika.Message(json.dumps(all_sites).encode()), routing_key='sites')
                    await asyncio.sleep(60)

    except KeyboardInterrupt:
        return

@router.get('/historylist')
async def historylist():
    return FileResponse('templates/history.html')

@router.get('/')
async def login():
    return FileResponse('templates/login.html')

@router.get('/register')
async def register():
    return FileResponse('templates/register.html')

@router.get('/mainpage')
async def mainpage():
    return FileResponse('templates/mainpage.html')

@router.post('/reg')
async def reg(name=Form(), password=Form(), db:AsyncSession=Depends(get_db)):
    result=(await db.execute(select(User).filter(User.name==name))).first()
    if result:
        raise HTTPException(401,'Такой пользователь уже есть!')
    target=User(name=name, password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
    db.add(target)
    await db.commit()
    response=RedirectResponse('/',status_code=303)
    return response

@router.post('/login')
async def log(name=Form(), password=Form(), db:AsyncSession=Depends(get_db)):
    result=(await db.execute(select(User).filter(User.name==name))).first()
    if not(result):
        raise HTTPException(401,'Неправильный логин или пароль!')
    user=result[0]
    if not(bcrypt.checkpw(password.encode(), user.password.encode())):
        raise HTTPException(401,'Неправильный логин или пароль!')
    refresh=create_token(user.name,timedelta=timedelta(days=30))
    response=RedirectResponse('/mainpage',status_code=303)
    response.set_cookie('access_token', create_token(user.name,timedelta=timedelta(minutes=30)), path='/')
    response.set_cookie('refresh_token',refresh, path='/', max_age=3600*24*30)
    user.refresh_token=refresh
    await db.commit()
    return response

@router.post('/refresh')
async def refresh(refresh_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(refresh_token)
    if user.refresh_token!=refresh_token:
        raise HTTPException(401,'Проблема с токеном!')
    response=JSONResponse({'status':'ok'},status_code=200)
    response.set_cookie('access_token', create_token(user.name, timedelta=timedelta(minutes=30)))
    return response

@router.get('/products')
async def products(access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user= await get_by_token(access_token)
    data=await r.get(f'{user.name}:products')
    if data:
        return {'products':json.loads(data)}
    products=(await db.execute(select(Site).filter(Site.user_id==user.id))).all()
    all_products=[]
    for i in products:
        all_products.append({'status_code':str(i[0].status_code),'id':i[0].id,'name':i[0].title, 'current_price':str(i[0].last_price), 'target_price':str(i[0].wanted_price),'updated_at':str(i[0].last_seen.strftime("%Y.%m.%d %H:%M"))})
    await r.setex(f'{user.name}:products',60,json.dumps(all_products))
    return {'products':all_products}

@router.post('/products')
async def add_product(access_token=Cookie(), data=Body(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(access_token)
    target=Site(title=data['title'], url=data['url'], wanted_price=data['target_price'], user_id=user.id)
    db.add(target)
    await db.commit()
    await r.delete(f'{user.name}:products')

@router.delete('/products/{id}')
async def delete_products(id:int, access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(access_token)
    result=(await db.execute(select(Site).filter(Site.id==id))).first()
    if not(result):
        raise HTTPException(404,'Такого продукта не существует!')
    if result[0].user_id!=user.id:
        raise HTTPException(404,'Такого продукта не существует!')
    await db.delete(result[0])
    await db.commit()
    await r.delete(f'{user.name}:products')

@router.post('/history')
async def history(access_token=Cookie(), db:AsyncSession=Depends(get_db), period=Query(), current=Body()):
    user=await get_by_token(access_token)
    data=await r.get(f'{user.name}:history')
    if data:
        return {'history':json.loads(data)}
    if period=='all':
        products = (await db.execute(
            select(Site.title, History.created_at, History.price)
            .join(History,Site.id==History.sites_id)
            .filter(Site.user_id==user.id)
            .order_by(desc(History.created_at))
            .limit(int(current['page'])*20)
        )).all()
    else:
        products = (await db.execute(
            select(Site.title, History.created_at, History.price)
            .join(History,Site.id==History.sites_id)
            .filter(Site.user_id==user.id, History.created_at>=datetime.now()-timedelta(days=int(period)))
            .order_by(desc(History.created_at))
            .limit(int(current['page'])*20)
        )).all()
    history_products=[]
    for i in products:
        history_products.append({'product_name':str(i[0]),'price':str(i[2]),'checked_at':str(i[1].strftime("%Y.%m.%d %H:%M"))})
    await r.setex(f'{user.name}',60, json.dumps(history_products))
    return {'history':history_products}

@router.get('/logout')
async def logout():
    response=RedirectResponse('/',status_code=303)
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    return response


