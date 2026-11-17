# это бекенд
from fastapi import FastAPI, HTTPException
import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

# Настройки берутся из .env локально и из переменных Amvera в облаке.
PROJECT_ROOT = Path(__file__).resolve().parents[1] # поднимаемся от файла на ступень выше
load_dotenv(PROJECT_ROOT / '.env') # как поднялись к .env путем поднятия (проджект рут) читаем файл в котором токены и тп

# Локально база рядом с этим файлом; в Amvera DATABASE_PATH задаётся как /data/database.db.
DB_PATH = os.getenv( # мы успешно поднялись к env и оттуда берем наш пуит по API, а от API он нам дает бд создать в /дата
    'DATABASE_PATH', # либо берем заданный параметр от облака (переменная)
    str(Path(__file__).resolve().with_name('database.db')) # в ином случае создаем / берем файл рядом с main.py
) 

app = FastAPI()

# ИНФО
# 1) Тут тоже присутсвует необходимая валидация данных, не только со стороны бота. 
# 2) Все разделенно на отдельные части.

# ========== создание таблиц (подгрузка для сервера еще)==========

def init_db():
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # таблица всех юзеров
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        joined_at TEXT
        )
    ''')

    # таблица всех листов (связан с юзером)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        created_at TEXT,
        status INTEGER DEFAULT 0,
        total_cost INTEGER
        )
    ''')

    # таблица всех айтемов (связан с листом)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER,
        name TEXT,
        is_bought INTEGER DEFAULT 0
        )
    ''')

    print('успешно.')
    conn.commit()
    conn.close()

init_db() # запускать каждый раз в проге

# ========== работа с юзером ==========

@app.post('/users') # добавление пользователя в систему
def add_user(telegram_id: int, joined_at: str):
    if telegram_id <= 0: # проверка на телеграм id
        return {"status": "error", "message": "telegram_id должен быть положительным"}

    if not joined_at or not joined_at.strip(): # проверка на дату присоединения
        return {"status": "error", "message": "дата регистрации не может быть пустой"}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # проверка есть ли телеграм айди уже или не
    cursor.execute('SELECT telegram_id FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone() 

    if not user: # если нету то добавляем
        cursor.execute('INSERT INTO users (telegram_id, joined_at) VALUES (?, ?)', (telegram_id, joined_at))
        conn.commit()
        conn.close()
        return {"status": "created"}
    else:
        conn.close()
        return {"status": "already_exists"}

@app.get('/users/{telegram_id}') # получить инфу о юзере
def get_user(telegram_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    data = cursor.fetchone()
    conn.close()

    if data:
        return {"data": data} # требуется [0] тк без них отдадим тепл (то есть со скобками и с запятой). возвращаем дату
    else:
        return {"data": "ошибка!"}

@app.get('/users')
def get_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()

    conn.close()
    return users


@app.get('/users/{user_id}/lists') # получить все списки зная АЙДИ ЮЗЕРА
def get_lists(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM lists WHERE user_id = ?', (user_id,))
    lists = cursor.fetchall()

    conn.close()
    if lists:
        return lists
    else:
        return []

@app.get('/users/{user_id}/items') # получить все айтемы зная АЙДИ ЮЗЕРА
def get_user_items(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Склеиваем (JOIN) колонку list_id в items с колонкой id в lists
    # 2. ну и тк у нас SELECT мы берем то, где в системе lists по юзер айди совпадает ???

    cursor.execute('''
    SELECT items.*
    FROM items
    JOIN lists ON items.list_id = lists.id
    WHERE lists.user_id = ?
    ''', (user_id,))
    items = cursor.fetchall()

    conn.close()
    if items:
        return items
    else:
        return []

# ========== работа с листами ==========

@app.post('/lists') # добавить список
def add_list(user_id: int, name: str, created_at: str, total_cost: int):
    if not name or not name.strip(): # проверка на название списка
        return {"status": "error", "message": "имя списка не может быть пустым"}

    if total_cost < 0: # проверка на стоимость
        return {"status": "error", "message": "чек не может быть отрицательным"}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('INSERT INTO lists (user_id, name, created_at, total_cost) VALUES (?, ?, ?, ?)', (user_id, name, created_at, total_cost))
    conn.commit()

    new_list_id = cursor.lastrowid 
    conn.close()

    return {"status": "created", "list_id": new_list_id}  

@app.get('/lists/by_id/{id}') # получить имя зная АЙДИ ЛИСТА
def get_list_name(id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT name FROM lists WHERE id = ?', (id,))
    list_name = cursor.fetchone()

    conn.close()
    if list_name:
        return {"list_name": list_name[0]}
    else:
        return {"list_id": None}

@app.get('/lists/user_id/{list_id}') # получить юзер айди зная лист
def get_user_id(list_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM lists WHERE id = ?', (list_id,))
    user_id = cursor.fetchone()

    conn.close()
    if user_id:
        return {"user_id": user_id[0]}  # ✅
    else:
        return {"user_id": None}

@app.delete('/lists/{list_id}') # удалить
def delete_list(list_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM items WHERE list_id = ?', (list_id,))
    cursor.execute('DELETE FROM lists WHERE id = ?', (list_id,))
    conn.commit()
    conn.close()

    return {"status": "deleted"}

@app.get('/lists/{list_id}/created_at') # взять дату создания
def created_at_list(list_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT created_at FROM lists WHERE id = ?', (list_id,))
    created_at = cursor.fetchone()

    conn.close()
    if created_at:
        return {"created_at": created_at[0]}
    else:
        return {"created_at": "неизвестно"}


@app.put('/lists/complete/{list_id}') # завершить и добавить чек
def complete_list(list_id: int, total_cost: int):
    if total_cost < 0:
        return {"status": "error", "message": "чек не может быть отрицательным"}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('UPDATE lists SET status = 1, total_cost = ? WHERE id = ?', (total_cost, list_id))

    conn.commit()
    conn.close()
    return {"status": "finished"}

@app.put('/lists/items/check/{list_id}')
def check_list(list_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Просто обновляем все предметы конкретного списка
    cursor.execute('UPDATE items SET is_bought = 1 WHERE list_id = ?', (list_id,))
    
    conn.commit()
    conn.close()
    return {"status": "checked_all"}

# ========== работа с айтемами ==========

@app.get('/items/{item_id}/list_id') # получить айди листа зная АЙДИ АЙТЕМА (привязанного к листу)
def get_list_byitem(item_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT list_id FROM items WHERE id = ?', (item_id,))
    list_id = cursor.fetchone()

    conn.close()
    return {"list_id": list_id[0]}

@app.post('/items')
def add_item(list_id: int, name: str):
    if not name or not name.strip(): # проверка имени
        return {"status": "error", "message": "имя предмета не может быть пустым"}

    if list_id <= 0: # проверка айди
        return {"status": "error", "message": "некорректный list_id"}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM lists WHERE id = ?', (list_id,))
    if not cursor.fetchone():
        conn.close()
        return {"status": "error", "message": "список не найден"}

    cursor.execute('INSERT INTO items (list_id, name) VALUES (?, ?)', (list_id, name)) # is bought безмысленно тк базово там 0

    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get('/items') # получить айтемы из списка
def get_items(list_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM items WHERE list_id = ?', (list_id,))
    items = cursor.fetchall()

    conn.close()
    if items:
        return items
    else:
        return []

@app.delete('/items/{item_id}') # удалить предмет
def del_item(item_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM items WHERE id = ?', (item_id,))  # ✅

    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.put('/item/check/{item_id}') # меняем значаение is_bought
def check_item(item_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT is_bought FROM items WHERE id = ?', (item_id,))
    current = cursor.fetchone() # получили что сейчас current

    if current:
        if current[0] == 0: # тк делаем систему тоггл то если сейчас у нас 0
            new_status = 1 # то статус меняем на 1
        else: # если там 1 
            new_status = 0 # то ставим 0
        cursor.execute('UPDATE items SET is_bought = ? WHERE id = ?', (new_status, item_id))
        conn.commit()

    conn.close()
    return {"status": "checked"}  # ✅