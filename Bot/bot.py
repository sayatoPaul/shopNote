from aiogram import Dispatcher, Bot
import asyncio
import requests # для будущего бекенда, но пока юзлесс
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ============ троттлинг (защита от спама. я просто скопировал готовый код) =============
import time
from aiogram import BaseMiddleware
from aiogram.types import Message

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit # секунд между сообщениями
        self.users = {}

    async def __call__(self, handler, event: Message, data):
        user_id = event.from_user.id
        current_time = time.time()

        # Если пользователь писал меньше rate_limit секунд назад — игнорируем
        if user_id in self.users:
            last_time = self.users[user_id]
            if current_time - last_time < self.rate_limit:
                return # Просто игнорируем сообщение (бот не отвечает)
        
        self.users[user_id] = current_time
        return await handler(event, data)
# ============ конец троттлинга (защита от спама) =============

from config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()
dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5)) # включаем троттлинг. 0.5 секунды между командами

# ============= Создаем состояния =============

class AddListStates(StatesGroup): # короче создаем класс и он вид СтэйтсГроуп. 
    waiting_for_name = State() # создаем состояние ожидания названия
    waiting_for_items = State()
    waiting_for_new_item = State()
    waiting_for_remove_item = State()
    waiting_for_check = State()

# ============== хендлер /start ==============

@dp.message(Command('start'))
async def start_handler(message: Message):
    # добавления юзера в БД

    user_id = message.from_user.id
    from datetime import datetime
    joined_at = datetime.now().strftime("%Y-%m-%d")

    response = requests.post('http://localhost:8000/users', params={"telegram_id": user_id, "joined_at": joined_at})

    # вывод кнопок снизу. реплайкейборд
    keyboard = ReplyKeyboardMarkup(

        keyboard=[
            [KeyboardButton(text='Мои списки'),
            KeyboardButton(text='Написать список')],
            [KeyboardButton(text='Профиль')]
        ], resize_keyboard=True
    )

    # ответ. привествие
    await message.answer(f'''
<b>shopNote.</b>\n
<blockquote>я понимаю твою боль, когда ты засоряешь свой чат «избранное» или заметки телефона списками для покупок. я здесь, чтобы решить твои проблемы.</blockquote>

<b>функционал прост:</b>

<b>история:</b>  
— показывает все твои списки. удобно, когда интересно, что ты покупаешь на протяжении долгого времени. а может, тебя заинтересует статистика.

<b>написать список</b>  
— открывает режим быстрого заполнения списка. ничего лишнего — название и написание списка. каждая покупка — новая строчка.

<b>статистика:</b>
— твой профиль. суммарная трата денег, количество покупок (одна строчка = одна покупка). в общем, интересно.\n
<i>bot's created by Paul Sayato.</i>
''', reply_markup=keyboard, parse_mode='HTML')

# обработка кнопок снизу (реплай кейборд, т.е. тот что снизу)

# ============= ЧЕЛОВЕК НАЖИМАЕТ "Мои списки" =============

@dp.message(lambda message: message.text == 'Мои списки') # не рабочее
async def all_lists_handler(message: Message):
    user_id = message.from_user.id
    text, keyboard = get_lists_markup(user_id) # просто юзаю
    await message.answer(text, parse_mode='HTML', reply_markup=keyboard)

def get_lists_markup(user_id): # функция выполнения типо показ списков
    response = requests.get(f'http://localhost:8000/users/{user_id}/lists')
    lists = response.json()

    if lists:
        text = ''
        status = ''
        for i, list in enumerate(lists, 1):
            if list[4] == 1:
                status = '✅'
            elif list[4] == 0:
                status = '⏳'

            if status == '✅':
                text += f'<code>|{status}|</code> <b>№{i}.</b> <s>{list[2]}.</s>\n'
            elif status == '⏳':
                text += f'<code>|{status}|</code> <b>№{i}.</b> {list[2]}.\n'

        # создаем кнопочки если все ок базару нет
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="открыть список", callback_data=f"preopen_list_{user_id}"),
                InlineKeyboardButton(text="вернуться в меню", callback_data=f"return_menu_{user_id}")]
            ]
        )
        return f'<b>списки — ваша история:</b>\n\n{text} <blockquote>«✅» — покупки выполнены. \n«⏳» — покупки в процессе</blockquote>', keyboard

    else:
        # создаем кнопки если базар есть
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='написать список', callback_data=f'new_list_{user_id}'),
                InlineKeyboardButton(text='вернуться в меню', callback_data=f'return_menu_{user_id}')]
            ]
        )
        return f'<b>списки — ваша история:</b>\n\n<b>‼️ не нашлось списков!</b>\n<i>нажмите соответствующую кнопку для создания вашего первого списка покупок.</i>\n <blockquote>«✅» — покупки выполнены. \n«⏳» — покупки в процессе</blockquote>', keyboard



# ============= ЧЕЛОВЕК НАЖИМАЕТ "Написать список" =============

@dp.message(lambda message: message.text == 'Написать список') #
async def add_list_handler(message: Message, state: FSMContext):
    # включаем состояние ожидания названия
    await state.set_state(AddListStates.waiting_for_name) # добавляем состояние. В параметрах из списка пишем конкретное состояние
    await message.answer('введите имя списка:')


# СОСТОЯНИЕ по FSP ловим НАЗВАНИЕ списка. затем будем ждать предметы
@dp.message(AddListStates.waiting_for_name) 
async def process_name(message: Message, state: FSMContext):
    # сохраняем в память FSM название списка (для распоковки и использования в следующем обработчике)
    await state.update_data(list_name=message.text)
    list_name = message.text
    if not list_name.strip():
            await message.answer('<b>ошибка!</b>\nвведите <b>имя</b> списка!', parse_mode='HTML')
            await state.clear()
            return
    user_id = message.from_user.id
    from datetime import datetime
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")  # "2026-11-04 14:35"

    try:
        response = requests.post(f'http://localhost:8000/lists',
            params={
                'user_id': user_id,
                "name": list_name,
                "created_at": created_at,
                "total_cost": 0
            })  
        # включаем состояние ожидания ПРЕДМЕТОВ
        await state.set_state(AddListStates.waiting_for_items)
        await message.answer('<b>да!</b> теперь перечислите продукты:\n— <i>первый раз желательно написать всё <b>через строчку.</b> \n— если понадобится что-то добавить то <b>нажмите соответствующую кнопку</b> или просто <b>напишите в чате</b> новый продукт/предмет.</i>', parse_mode='HTML')
    except requests.ConnectionError:
        await message.answer('нет ответа с базой данных. не получилось сохранить')
        await state.clear()

# СОСТОЯНИЕ по FSP ловим ПРЕДМЕТЫ и тут же отвечаем кнопками. то есть черновик
@dp.message(AddListStates.waiting_for_items)
async def process_items(message: Message, state: FSMContext):
    # распаковка имени списка
    data = await state.get_data()
    list_name = data.get('list_name')

    # разбиваем продукты
    goods = message.text
    if not goods.strip():
            await message.answer('<b>ошибка!</b>\nвведите пункты!')
            await state.clear()
            return
    goods_list = goods.split('\n')

    # достать номер id листа к которому мы прикрепим
    response = requests.get(f'http://localhost:8000/lists/by_name/{list_name}') # ✅
    list_id = response.json()["list_id"]
    await state.update_data(edit_list_id=list_id)  # на будущее отправляем в данные
    if not list_id:
        await message.answer('Ошибка. Список не найден!')
        await state.clear()
        return

    # сохраняем в БД
    for item in goods_list:
        response = requests.post(f'http://localhost:8000/items', params={"list_id": list_id, "name": item})

    response = requests.get(f'http://localhost:8000/items', params={"list_id": list_id})
    items = response.json()

    # ответ
    text = ''
    for i, item in enumerate(items, 1):
        status = ''
        if item[3] == 0:
            status = '🚫' 
        else:
            status = '✅'
        text += f'<code>|{status}|</code> <b>№{i}.</b> {item[2]}.\n'

    # кнопки подготовка
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="сохранить список", callback_data=f"finish_list_{list_id}")],
            [InlineKeyboardButton(text="добавить предмет", callback_data=f"add_item_{list_id}"),
            InlineKeyboardButton(text="удалить предмет", callback_data=f"predelete_item_{list_id}")]
        ]
    )
    await state.update_data(list_name=list_name, edit_list_id=list_id)
    await message.answer(f"<b>черновик списка «{list_name}»</b>\n\n<b>вы добавили:</b>\n{text}",
                         parse_mode="HTML",
                         reply_markup=keyboard)

# CALLBACK_QUERY, обрабатываем кнопки от ФСПшки, которая принимает ПРЕДМЕТЫ. 
@dp.callback_query()
async def callback_handler(callback, state: FSMContext):
    # получение и обработка действия, объекта.
    try:
        # получаем
        data = callback.data

        # разбор
        parts = data.split('_') # обычно получаем типо add_list_{list_id}
        action = parts[0]
        object = parts[1]
    except (IndexError, ValueError):
        await callback.answer('кнопка устарела. начни заново.')
        return

    # короче обработка def all_lists_handler. тут add_list, open_list return_menu,
    if action == 'new' and object == 'list': # add_list_{user_id}
        await state.set_state(AddListStates.waiting_for_name)
        await callback.message.answer('<b>🎉 ваш первый список!</b>\nвведите название:', parse_mode='HTML')
        await callback.answer()
        return

    elif action == 'preopen' and object == 'list': # open_list_{user_id}
        user_id = int(parts[2])
            # получаем все листы
        response = requests.get(f'http://localhost:8000/users/{user_id}/lists')
        lists = response.json()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=str(i+1), callback_data=f'open_list_{list[0]}') for i, list in enumerate(lists)]
            ]
        )
        await callback.message.answer('выбери номер списка:', reply_markup=keyboard)
        await callback.answer()
        return

    elif action == 'open' and object == 'list': # open_list_{list[0]}
        list_id = int(parts[2])
        user_id = callback.from_user.id  # ✅ Получаем ID юзера
        # получаем имя списка
        response = requests.get(f'http://localhost:8000/lists/by_id/{list_id}') 
        list_name = response.json()["list_name"]
        # получаем все айтемы
        response = requests.get(f'http://localhost:8000/items', params={"list_id": list_id})
        items = response.json()

        if items:
            text = ''
            for i, item in enumerate(items, 1):
                status = ''
                if item[3] == 0:
                    status = '🚫' 
                    text += f'<code>|{status}|</code> <b>{i}.</b> {item[2]}\n'
                else:
                    status = '✅'
                    text += f'<code>|{status}|</code> <b>{i}.</b> <s>{item[2]}</s>\n'
        else:
            text = '‼️<b>не нашлось пунктов!</b>'

        # кнопки подготовка
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="закончить / обновить список", callback_data=f"complete_list_{list_id}")],

                [InlineKeyboardButton(text="вычеркнуть / вернуть", callback_data=f"precheck_item_{list_id}"),
                InlineKeyboardButton(text="редактировать", callback_data=f"edit_list_{list_id}")],
                
                [InlineKeyboardButton(text="открыть списки", callback_data=f"open_lists_{user_id}")]
            ]
        )

        # ✅ СОХРАНЯЕМ В FSM
        await state.update_data(edit_list_id=list_id, list_name=list_name)

        await callback.message.edit_text(f'<b>список:</b> «{list_name}»\n\n{text}', parse_mode='HTML', reply_markup=keyboard)

    elif action == 'complete' and object == 'list':
        list_id = int(parts[2])

        await callback.message.answer('<b>введите сумма чека:</b>\n<i>— если не помнишь чек / не нужно, то <b>впиши "0"</b>. иначе это сломает твою же удобность, ведь статистика полетит!</i>', parse_mode='HTML')
        await state.update_data(edit_list_id=list_id)
        await state.set_state(AddListStates.waiting_for_check)
        await callback.answer()
        return
            
    elif action == 'precheck' and object == 'item':
        list_id = int(parts[2])
        # получаем все продукты
        response = requests.get(f'http://localhost:8000/items', params={"list_id": list_id})
        items = response.json()

        if not items:
            await callback.message.answer('список пуст, чувак.')
            await callback.answer()
            return

        # формируем кнопки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                # по 3 кнопки в ряд
                [InlineKeyboardButton(text=str(i+1), callback_data=f'check_item_{item[0]}') for i, item in enumerate(items)],
                [InlineKeyboardButton(text='вычеркнуть всё', callback_data=f'checkall_list_{list_id}')]
                # так как джсон разбираем по item'у и берем фэйковый айдишник по порядку предмета, а настроящий из джсона [0]
            ]
        )
        await callback.message.answer('выбери номер пункта:', reply_markup=keyboard)
        await callback.answer()

    elif action == 'checkall' and object == 'list':
        list_id = int(parts[2])
        user_id = callback.from_user.id
        
        response = requests.put(f'http://localhost:8000/lists/items/check/{list_id}')

        if response.status_code == 200:
            # Отправляем ОБНОВЛЕННЫЙ СПИСОК

            # list_name
            response = requests.get(f'http://localhost:8000/lists/by_id/{list_id}') 
            list_name = response.json()["list_name"]

            # получаем все айтемы
            response = requests.get(f'http://localhost:8000/items', params={"list_id": list_id})
            items = response.json()
    
            text = ''
            for i, item in enumerate(items, 1):
                status = ''
                if item[3] == 0:
                    status = '🚫' 
                    text += f'<code>|{status}|</code> <b>{i}.</b> {item[2]}\n'
                else:
                    status = '✅'
                    text += f'<code>|{status}|</code> <b>{i}.</b> <s>{item[2]}</s>\n'
                    
        
            # кнопки подготовка
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="закончить / обновить список", callback_data=f"complete_list_{list_id}")],
                    
                    [InlineKeyboardButton(text="вычеркнуть / вернуть", callback_data=f"precheck_item_{list_id}"),
                    InlineKeyboardButton(text="редактировать", callback_data=f"edit_list_{list_id}")], 
                    
                    [InlineKeyboardButton(text="открыть списки", callback_data=f"open_lists_{user_id}")] # ✅
                ]
            )
            await callback.message.edit_text(f'<b>список:</b> «{list_name}»\n\n{text}', parse_mode='HTML', reply_markup=keyboard)
            await callback.answer()
            return
        else:
            await callback.message.answer('это фиаско, братан.')
            await callback.answer()
            return

    elif action == 'check' and object == 'item':
        item_id = int(parts[2])
        user_id = callback.from_user.id  # ✅ Получаем ID
        response = requests.put(f'http://localhost:8000/item/check/{item_id}', params={"item_id": item_id})

        if response.status_code == 200:
            # Отправляем ОБНОВЛЕННЫЙ СПИСОК

            # list_id
            response = requests.get(f'http://localhost:8000/items/{item_id}/list_id')
            list_id = response.json()["list_id"]

            # list_name
            response = requests.get(f'http://localhost:8000/lists/by_id/{list_id}') 
            list_name = response.json()["list_name"]

            # получаем все айтемы
            response = requests.get(f'http://localhost:8000/items', params={"list_id": list_id})
            items = response.json()
    
            text = ''
            for i, item in enumerate(items, 1):
                status = ''
                if item[3] == 0:
                    status = '🚫' 
                    text += f'<code>|{status}|</code> <b>{i}.</b> {item[2]}\n'
                else:
                    status = '✅'
                    text += f'<code>|{status}|</code> <b>{i}.</b> <s>{item[2]}</s>\n'
                    
        
            # кнопки подготовка
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="закончить / обновить список", callback_data=f"complete_list_{list_id}")],
                    
                    [InlineKeyboardButton(text="вычеркнуть / вернуть", callback_data=f"precheck_item_{list_id}"),
                    InlineKeyboardButton(text="редактировать", callback_data=f"edit_list_{list_id}")], 
                    
                    [InlineKeyboardButton(text="открыть списки", callback_data=f"open_lists_{user_id}")] # ✅
                ]
            )
            await callback.message.edit_text(f'<b>список:</b> «{list_name}»\n\n{text}', parse_mode='HTML', reply_markup=keyboard)
            await callback.answer()
            return
        else:
            await callback.message.answer('это фиаско, братан.')
            await callback.answer()
            return

    elif action == 'edit' and object == 'list':
        list_id = int(parts[2])
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="добавить пункт", callback_data=f'add_item_{list_id}')], # переброс уже на существующую функцию
                
                [InlineKeyboardButton(text="удалить пункт", callback_data=f'predelete_item_{list_id}'), # переброс на удаление
                InlineKeyboardButton(text="стереть список", callback_data=f"delete_list_{list_id}")],

                [InlineKeyboardButton(text="вернуться ко списку", callback_data=f"open_list_{list_id}")]
            ]
        )

        # list_name
        response = requests.get(f'http://localhost:8000/lists/by_id/{list_id}') 
        list_name = response.json()["list_name"]

        # получаем все айтемы
        response = requests.get(f'http://localhost:8000/items', params={"list_id": list_id})
        items = response.json()

        text = ''
        for i, item in enumerate(items, 1):
            status = ''
            if item[3] == 0:
                status = '🚫' 
                text += f'<code>|{status}|</code> <b>{i}.</b> {item[2]}\n'
            else:
                status = '✅'
                text += f'<code>|{status}|</code> <b>{i}.</b> <s>{item[2]}</s>\n'

        # ✅ СОХРАНЯЕМ В FSM
        await state.update_data(edit_list_id=list_id, list_name=list_name)

        await callback.message.edit_text(f'<b>✏️ редакция:</b> «{list_name}»\n\n{text}', parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return

    elif action == 'delete' and object == 'list':
        list_id = int(parts[2])

        response = requests.get(f'http://localhost:8000/lists/user_id/{list_id}')
        user_id = response.json()["user_id"]

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='вернуться ко спискам', callback_data=f'open_lists_{user_id}')]
            ]
        )

        response = requests.delete(f'http://localhost:8000/lists/{list_id}')

        if response.status_code == 200:
            await callback.message.edit_text('🗑 <b>cписок полностью удален!</b>', parse_mode='HTML', reply_markup=keyboard)
            await callback.answer()
            return
        else:
            await callback.message.answer('ошибка при удалении. попробуй позже.')
            await callback.answer()
            return

    elif action == 'open' and object == 'lists':
        user_id = int(parts[2])
        text, keyboard = get_lists_markup(user_id)
        await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard) 
        await callback.answer()
        return

    elif action == 'return' and object == 'menu': # return_menu_{user_id}
        await start_handler(callback.message)
        await callback.answer()
        return

    # если нажимается кнопка "Закончить список". Выходим
    elif action == 'finish' and object == 'list':
        list_id = int(parts[2])
        user_id = callback.from_user.id

        keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text='вернуться к спискам', callback_data=f"open_lists_{user_id}")]
                ]
            )

        await callback.message.edit_text('<b>список написан!</b>\n — его полностью можно увидеть по кнопке ниже либо в истории. редактировать, вычёркивать продукты или удалить его можно при просмотре в открытом виде.', parse_mode="HTML", reply_markup=keyboard)
        await state.clear()  # ✅ ВАЖНО
        await callback.answer()
        return

    # если нажимается кнопка "Создать". Входим в состояния ожидания
    elif action == 'add' and object == 'item':
        list_id = int(parts[2])
        # Данные (list_name, edit_list_id) уже в FSM!
        await state.set_state(AddListStates.waiting_for_new_item)
        await callback.message.answer('введи новый пункт:')
        await callback.answer()

    # если нажимается кнопка "Удалить". Отправляем список пунктов
    elif action == 'predelete' and object == 'item':
        list_id = int(parts[2])
        
        # ✅ 1. Получаем имя списка с бэкенда
        response = requests.get(f'http://localhost:8000/lists/by_id/{list_id}') 
        list_name = response.json()["list_name"]
    
        # ✅ 2. Сохраняем И ID, И имя в FSM
        await state.update_data(edit_list_id=list_id, list_name=list_name) 

        # получаем все продукты
        response = requests.get(f'http://localhost:8000/items', params={"list_id": list_id})
        items = response.json()

        if not items:
            await callback.message.answer('список пуст, чувак.')
            await callback.answer()
            return

        # формируем кнопки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                # по 3 кнопки в ряд
                [InlineKeyboardButton(text=str(i+1), callback_data=f'delete_item_{item[0]}') for i, item in enumerate(items)] 
                # так как джсон разбираем по item'у и берем фэйковый айдишник по порядку предмета, а настроящий из джсона [0]
            ]
        )
        await callback.message.answer('выбери номер пункта:', reply_markup=keyboard)
        await callback.answer()

    # в списке выбераем пункт. Удаляем. Шлем обновленный список
    elif action == 'delete' and object == 'item':
        item_id = int(parts[2])
        response = requests.delete(f'http://localhost:8000/items/{item_id}')

        if response.status_code != 200:
            await callback.message.answer(f'<b>error:</b> {response.status_code}\n — это фиаско, братан. ', parse_mode='HTML')

        data = await state.get_data()
        list_id = data.get('edit_list_id')
        list_name = data.get('list_name')

        # обновляем че есть теперь в задачах    
        response = requests.get('http://localhost:8000/items', params={'list_id': list_id})
        items = response.json()
        # готовим список задач
        text = ''
        for i, item in enumerate(items, 1):
            status = ''
            if item[3] == 0:
                status = '🚫' 
            else:
                status = '✅'
            text += f'<code>|{status}|</code> <b>{i}.</b> {item[2]}\n'
    
        # кнопки подготовка
        keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="добавить предмет", callback_data=f"add_item_{list_id}"),
                InlineKeyboardButton(text="удалить предмет", callback_data=f"predelete_item_{list_id}"),
                InlineKeyboardButton(text="стереть список", callback_data=f"delete_list_{list_id}")
            ],
            [InlineKeyboardButton(text="вернуться ко списку", callback_data=f"open_list_{list_id}")]
        ]
        )
        # шлем текст
        await callback.message.edit_text(f"<b>✏️ редакция списка: «{list_name}»</b>\n\n<b>Пункты:</b>\n\n{text}", parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()     

@dp.message(AddListStates.waiting_for_check)
async def get_check(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    list_id = data.get('edit_list_id')
    try:
        check = int(message.text)
    except:
        await message.answer('цифры писать надо!')
        await state.clear()
        return

    # завершаем
    response = requests.put(f'http://localhost:8000/lists/complete/{list_id}', params={'total_cost': check})

    # кол-во предметов
    response = requests.get('http://localhost:8000/items', params={'list_id': list_id})
    items = response.json()

    # дата
    response = requests.get(f'http://localhost:8000/lists/{list_id}/created_at')
    created_at = response.json()["created_at"]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='вернуться к спискам', callback_data=f"open_lists_{user_id}")]
        ]
    )

    succes_items = 0
    for item in items:
        if item[3] == 1:
            succes_items += 1

    await message.answer(f'''
<b>список завершен.</b>\n
<b>— кол-во купленных пунктов:</b> {succes_items} / {len(items)} шт.
<b>— чек:</b> {check} ₽
<b>— создан:</b> {created_at}
''', parse_mode='HTML', reply_markup=keyboard)
    await state.clear()
    return

# СОСТОЯНИЕ. ТУТ ПРИНИМАЕМ СООБЩЕНИЕ. Продолжение "Создания предмета"
@dp.message(AddListStates.waiting_for_new_item)
async def process_item(message: Message, state: FSMContext):
    data = await state.get_data() # Данные (list_name, edit_list_id) уже в FSM!
    list_id = data.get('edit_list_id') # так как мы сохраняли edit_list_id
    list_name = data.get('list_name')
    new_item = message.text

    response = requests.post('http://localhost:8000/items', params={'list_id': list_id, 'name': new_item})

    await message.answer(f'пункт «{new_item}» добавлен!')

    response = requests.get('http://localhost:8000/items', params={'list_id': list_id})
    items = response.json()
    text = ''
    for i, item in enumerate(items, 1):
        status = ''
        if item[3] == 0:
            status = '🚫' 
        else:
            status = '✅'
        text += f'<code>|{status}|</code> <b>{i}.</b> {item[2]}\n'

    # кнопки подготовка
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="добавить предмет", callback_data=f"add_item_{list_id}")],
            [InlineKeyboardButton(text="удалить предмет", callback_data=f"predelete_item_{list_id}")],
            [InlineKeyboardButton(text="стереть список", callback_data=f"delete_list_{list_id}")],
            [InlineKeyboardButton(text="вернуться ко списку", callback_data=f"open_list_{list_id}")]
        ]
    )

    await message.answer(f"<b>✏️ редакция списка: «{list_name}»</b>\n\n<b>ваши пункты:</b>\n{text}", parse_mode="HTML", reply_markup=keyboard)
    await state.clear()  # ✅ Ты очищаешь
    return
# ============== ЧЕЛОВЕК НАЖИМАЕТ "Профиль" ==============

@dp.message(lambda message: message.text == 'Профиль')
async def user_handler(message: Message):
    user_id = message.from_user.id
    user_photos = await bot.get_user_profile_photos(user_id)
    joined_at = "неизвестно"

    try:
        response = requests.get(f'http://localhost:8000/users/{user_id}')
        if response.status_code == 200:
            data = response.json() # это словарь {"data": [id, дата]}
            joined_at = data["data"][1] # ✅ Достаем список, затем второй элемент (дату)
    except requests.ConnectionError:
        pass

    response = requests.get(f'http://localhost:8000/users/{user_id}/lists')
    lists = response.json()


    response = requests.get(f'http://localhost:8000/users/{user_id}/items')
    items = response.json()

    succes_items = 0
    for item in items:
        if item[3] == 1:
            succes_items += 1 

    succes_lists = 0
    total = 0
    for list in lists:
        if list[4] == 1:
            succes_lists += 1
        total += list[5]

    text = f'''
<b>👤 ваш профиль:</b>\n
<b>📊 статистика</b>
• кол-во закрытых списков: {succes_lists} / {len(lists)} шт.
• кол-во завершенных пунктов: {succes_items} / {len(items)} шт.
• всего трат: {total} ₽\n
<b>ℹ️ информация</b>
• присоединился/ась: {joined_at}
• индивидуальный id: {user_id}\n
<i>bot's created by Paul Sayato.</i>
'''

    if user_photos.total_count == 0:
        await message.answer(text, parse_mode='HTML')
    else:
        photo = user_photos.photos[0][-1]
        await message.answer_photo(
            photo.file_id,
            caption=text,
            parse_mode='HTML'
        )

# хендлеры прочие

# admin stuff

@dp.message(Command('get_users'))
async def get_users_handler(message: Message):
    try:
        response = requests.get('http://localhost:8000/users')
        data = response.json()  # ✅ превращаем в список
        await message.answer(str(data))  # ✅ превращаем в строку
    except requests.ConnectionError:
        await message.answer("Сервер недоступен.")


# ЗАПУСК БОТА

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())