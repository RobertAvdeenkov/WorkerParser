from aiogram import Bot,Dispatcher,types,F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import SessionLocal
from sqlalchemy import select,desc
from models import User,History
import bcrypt
from sqlalchemy.orm import selectinload
from fastapi import FastAPI

app=FastAPI()

class Form(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

Token='8930739545:AAGjEAlHHS8RCbvbxtBKDXYVEpB5CYYFMy8'

bot=Bot(token=Token)
db=Dispatcher()

@db.message(F.text=='/start')
async def answer(message: types.Message):
    await message.answer('Добро пожаловать в тг-бота сайта\nhttps://steamparser.onrender.com/\nВведите /login, чтобы войти в аккаунт\n')

@db.message(F.text=='/login')
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
        await message.answer(f'Здравствуйте, {user.name}\nДля того, чтобы посмотреть историю парсера, введите /history')

@db.message(F.text=='/history')
async def history(message:types.Message, state:FSMContext):
    data=await state.get_data()
    id_data=data.get('user_id')
    if not id_data:
        await message.answer('Вы не вошли в аккаунт! Чтобы войти введите /login')
        return
    id=int(id_data) #type:ignore
    txt='История за все время:\n\n\n'
    async with SessionLocal() as db: #type:ignore
        result=(await db.execute(select(History).filter(History.user_id==int(id)).options(selectinload(History.site)).order_by(desc(History.created_at)))).all()
        if result:
            for i in result:
                history_site=i[0]
                txt+=f'''
                {history_site.site.title}
                Статус код: {history_site.site.status_code}
                Цена: {history_site.price}
                Дата: {history_site.created_at.strftime("%Y.%m.%d %H:%M")}
                ---
                '''
        else: txt+='Ничего не найдено :('
    await message.answer(txt)

@app.on_event('startup')
async def main():
    print('started')
    await db.start_polling(bot)

@app.get('/')
async def root():
    return {'status':'ok'}