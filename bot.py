from aiogram import Bot,Dispatcher,types,F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from database import SessionLocal
from sqlalchemy import select,desc
from models import User,History
from aiogram.types import CallbackQuery
import bcrypt
from sqlalchemy.orm import selectinload
from fastapi import FastAPI
import asyncio
import os
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logger

tasks=set()

app=FastAPI()

class Form(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

Token=os.getenv('TOKEN')

bot=Bot(token=Token) #type:ignore
db=Dispatcher()

@db.message(Command('start'))
async def answer(message: types.Message, state:FSMContext):
    data=await state.get_data()
    if data.get('user_id'):
        await message.answer(f'Здравствуйте, {data.get('login')}\nДля того, чтобы посмотреть историю парсера, введите /history')
    else:
        await message.answer('Добро пожаловать в тг-бота сайта\nhttps://steamparser.onrender.com/\nВведите /login, чтобы войти в аккаунт\n')

@db.message(Command('login'))
async def login(message:types.Message, state:FSMContext):
    await message.answer('Введите логин:')
    await state.set_state(Form.waiting_for_login) #type:ignore

@db.message(Form.waiting_for_login)
async def enterlogin(message:types.Message, state:FSMContext):
    await state.update_data(login=message.text)
    await message.answer('Введите пароль:')
    await state.set_state(Form.waiting_for_password) #type:ignore

@db.message(Form.waiting_for_password)
async def enterpassword(message:types.Message, state:FSMContext):
    if not message:
        return
    data=await state.get_data()
    login=data.get('login')
    password=message.text
    async with SessionLocal() as db: #type:ignore
        result=(await db.execute(select(User).filter(User.name==login))).first()
        if not result:
            await state.clear()
            await message.answer('Неправильный логин или пароль!')
            return
        user=result[0]
        if not(bcrypt.checkpw(password.encode(), user.password.encode())): #type:ignore
            await state.clear()
            await message.answer('Неправильный логин или пароль!')
            return
        await state.update_data(user_id=user.id)
        await state.update_data(page=0)
        await state.set_state(None)
        user.tg_id=message.from_user.id #type:ignore
        await message.answer(f'Здравствуйте, {user.name}\nКоманды:\n/history - история парсера\n/logout - выход из аккаунта\n/settings - настройки')
        await db.commit()

async def historyLogic(message:types.Message | None, state:FSMContext):
    data=await state.get_data()
    id_data=data.get('user_id')
    if not id_data:
        await message.answer('Вы не вошли в аккаунт! Чтобы войти введите /login') #type:ignore
        return
    id=int(id_data) #type:ignore
    page=int(data.get('page')) #type:ignore
    txt='История за все время:\n\n\n'

    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="back")
    builder.button(text="Вперед", callback_data="next")
    builder.adjust(2)

    async with SessionLocal() as db: #type:ignore
        result=(await db.execute(select(History).filter(History.user_id==int(id)).options(selectinload(History.site)).offset(page*10).limit(10).order_by(desc(History.created_at)))).all()
        if result:
            for i in result:
                history_site=i[0]
                try:
                    txt+=f'''
                    {history_site.site.title}
                    Статус код: {history_site.site.status_code}
                    Цена: {history_site.price}
                    Дата: {history_site.created_at.strftime("%Y.%m.%d %H:%M")}
                    ---
                    '''
                except: pass
        else: txt+='Ничего не найдено :('
        txt+=f'\nСтраница {page}'
    await message.answer(txt, reply_markup=builder.as_markup()) #type:ignore
    return

@db.message(Command('history'))
async def history(message:types.Message, state:FSMContext):
    await state.update_data(page=1)
    await historyLogic(message=message, state=state) #type:ignore

@db.message(F.data=='back')
async def prev(message:types.Message, state:FSMContext):
    data= await state.get_data()
    page=data.get('page')
    if not page: return
    if int(page)-1<=0:
        await message.answer('Предыдущих страниц нет!')
    await state.update_data(page=int(page)-1)
    await historyLogic(message=message, state=state) #type:ignore

@db.message(F.data=='next')
async def nextpage(message:types.Message, state:FSMContext):
    data= await state.get_data()
    page=data.get('page')
    if not page: return
    await state.update_data(page=int(page)+1)
    await historyLogic(message=message, state=state) #type:ignore

@db.message(Command('logout'))
async def logout( message:types.Message, state:FSMContext):
    await state.clear()
    await message.answer(f'Вы вышли из аккаунта')
    return

@db.message(Command('settings'))
async def setting(message:types.Message, state:FSMContext):
    if not message: return
    data=await state.get_data()
    user_id=data.get('user_id')
    if not user_id:
        await message.answer('Вы не вошли в аккаунт! Чтобы войти введите /login') #type:ignore
        return
    async with SessionLocal() as db: #type:ignore
        user=await(db.execute(select(User).filter(User.id==int(user_id)))).first()
        if not user:
            await message.answer('Такого пользователя нет!')
            return
    builder = InlineKeyboardBuilder()
    builder.button(text="Включить сообщения" if not(user.message_on) else 'Выключить сообщения', callback_data="setting_messages")
    builder.adjust(1)
    await message.answer('НАСТРОЙКИ', reply_markup=builder.as_markup())
    return

@db.message(F.data=='setting_messages')
async def setting_messages(message:types.Message, state:FSMContext):
    if not message: return
    data=await state.get_data()
    user_id=data.get('user_id')
    if not user_id:
        await message.answer('Вы не вошли в аккаунт! Чтобы войти введите /login') #type:ignore
        return
    async with SessionLocal() as db: #type:ignore
        user=await(db.execute(select(User).filter(User.id==int(user_id)))).first()
        if not user:
            await message.answer('Такого пользователя нет!')
            return
    if user.message_on:
        user.message_on=False
    else:
        user.message_on=True
    await db.commit()
    await message.answer('Успешно!')
    return

@app.on_event('startup')
async def main():
    logger.logger.info('Started Telegram Bot')
    await bot.delete_webhook(drop_pending_updates=True)
    task = asyncio.create_task(db.start_polling(bot))
    tasks.add(task)
    task.add_done_callback(tasks.discard)

@app.get('/')
async def root():
    return {'status':'ok'}