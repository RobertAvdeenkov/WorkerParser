from sqlalchemy import Column,String,Integer,DateTime,ForeignKey,func
from sqlalchemy.orm import relationship,DeclarativeBase

class Base(DeclarativeBase):pass

class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True)
    name=Column(String)
    password=Column(String)
    refresh_token=Column(String)

    sites=relationship('Site', back_populates='user')
    history=relationship('History', back_populates='user')

class Site(Base):
    __tablename__='sites'
    id=Column(Integer,primary_key=True)
    title=Column(String)
    url=Column(String)
    user_id=Column(Integer, ForeignKey('users.id'))
    status_code=Column(Integer, default=200)

    last_seen=Column(DateTime,default=func.now())
    wanted_price=Column(Integer, default=0)
    last_price=Column(Integer, default=0)

    user=relationship('User', back_populates='sites')
    history=relationship('History', back_populates='site')

class History(Base):
    __tablename__='history'
    id=Column(Integer,primary_key=True)
    price=Column(Integer)
    created_at=Column(DateTime, default=func.now())

    user_id=Column(Integer, ForeignKey('users.id'))
    sites_id=Column(Integer, ForeignKey('sites.id'))

    user=relationship('User', back_populates='history')
    site=relationship('Site', back_populates='history')