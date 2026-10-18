from jose import jwt,JWTError,ExpiredSignatureError
from database import SessionLocal
from sqlalchemy import select
from models import User
from datetime import datetime
import os
from fastapi import HTTPException

SECRET=os.getenv('SECRET')
ALGORITHM=os.getenv('ALGORITHM')

def create_token(user:str, timedelta):
    payload={
        'sub':user,
        'exp':datetime.now()+timedelta
    }
    return jwt.encode(payload,SECRET,ALGORITHM) #type:ignore

async def get_by_token(token:str):
    try:
        name=jwt.decode(token,SECRET,algorithms=[ALGORITHM])['sub'] #type:ignore
        async with SessionLocal() as db: #type:ignore
            result=(await db.execute(select(User).filter(User.name==name))).first()
            if not result:
                raise HTTPException(404,'Такого пользователя нет!')
            return result[0]
    except ExpiredSignatureError:
        raise HTTPException(401,'Токен протух!')
    except JWTError:
        raise HTTPException(401,'Неправильный токен!')