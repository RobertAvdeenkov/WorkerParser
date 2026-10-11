Сервис для парсинга цен на товары стим.
Пользователь вводит ссылку, и RabbitMQ вокер парсит каждую минуту.
Есть возможность просматривать историю парсинга с пагинацией и сортировкой за последние день, неделю, месяц или за все время.
В проекте участвует кеширование для оптимизации и асинхронная БД.

## Технологии:
1. Python 3.14
2. RabbitMQ
3. Redis
4. FastAPI
5. Bcrypt
6. SQLAlchemy[asyncio]
7. Uvicorn
8. Python-jose[cryptography]

## Запуск:
1. Установите файлы
2. Установите библиотеки: pip install --no-cache-dir -r requirements.txt
3. Перейдите в папку
4. Запуск воркера и кеширования:
    1) docker run -d --name rabbitmq -p 5672:5672 rabbitmq:3.13 - запустить брокера
    2) docker run -p 6379:6379 --name redis -d redis:7-alpine - запустить Redis
4. В терминале введите: python -m uvicorn main:app --reload
5. После запуска в другом терминале: python worker.py