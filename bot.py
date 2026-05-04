import asyncio
import logging
from datetime import datetime, date
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN, ADMIN_IDS, DEFAULT_SUBJECTS
from database import Database
from parser import TimetableParser

import asyncio
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Измените на DEBUG для подробного логирования
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()
parser = TimetableParser()

# Машина состояний для админ-панели
class AdminState(StatesGroup):
    waiting_for_subject = State()
    waiting_for_hours = State()

# Проверка админа
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Команда /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    text = f"""
👋 Привет, {user.first_name}!

Я бот для учёта учебных пар.

📌 **Доступные команды:**
/today — расписание на сегодня
/date YYYY-MM-DD — расписание на дату
/stats — статистика по парам
/help — помощь

"""
    if is_admin(user.id):
        text += "🔑 **Вы администратор!**\n/admin — панель управления"
    
    await message.answer(text, parse_mode='Markdown')
    logger.info(f"Пользователь {user.id} запустил бота")

# Команда /help
@dp.message(Command('help'))
async def cmd_help(message: Message):
    text = """
📖 **Помощь**

**Для всех:**
/start — запуск бота
/today — расписание на сегодня
/date 2026-05-15 — расписание на дату
/stats — сколько осталось пар

**Для админа:**
/admin — панель управления
/set_subject 60 EH.01 — установить пары
/subjects — список предметов
/reset — сброс данных
"""
    await message.answer(text, parse_mode='Markdown')

# В команде /today добавьте логирование:
@dp.message(Command('today'))
async def cmd_today(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запросил расписание на сегодня")
    await message.answer("⏳ Загружаю расписание...")
    
    lessons = parser.get_timetable(date.today())
    
    if lessons:
        text = f"**📅 Расписание на сегодня**\n\n"
        text += parser.format_timetable(lessons)
        await message.answer(text, parse_mode='Markdown')
        logger.info(f"Отправлено расписание на сегодня: {len(lessons)} пар")
    else:
        await message.answer("❌ Не удалось получить расписание. Попробуйте позже.")
        logger.error("Не удалось получить расписание на сегодня")

# Команда /date
@dp.message(Command('date'))
async def cmd_date(message: Message):
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("📅 Используйте: /date YYYY-MM-DD\nПример: /date 2026-05-15")
            return
        
        target_date = datetime.strptime(args[1], '%Y-%m-%d').date()
        
        await message.answer("⏳ Загружаю расписание...")
        lessons = parser.get_timetable(target_date)
        
        if lessons:
            text = f"**📅 Расписание на {target_date}**\n\n"
            text += parser.format_timetable(lessons)
            await message.answer(text, parse_mode='Markdown')
        else:
            await message.answer("❌ Не удалось получить расписание. Попробуйте позже.")
            
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Ошибка команды /date: {e}")
        await message.answer("❌ Произошла ошибка")

# Команда /stats
@dp.message(Command('stats'))
async def cmd_stats(message: Message):
    await message.answer("⏳ Считаем статистику...")
    
    try:
        subjects = db.get_all_subjects()
        
        if not subjects:
            await message.answer(
                "📭 Нет данных о предметах.\n"
                "Администратор должен установить количество пар через /admin"
            )
            return
        
        # Получаем прошедшие пары
        passed = parser.get_passed_lessons()
        
        text = "📊 **Статистика по предметам**\n\n"
        
        for subject in subjects:
            total = subject['total_hours']
            code = subject['code']
            name = subject['name']
            passed_count = passed.get(code, 0)
            remaining = total - passed_count
            
            text += f"📘 **{name}** ({code})\n"
            text += f"   Всего: {total}\n"
            text += f"   Прошло: {passed_count}\n"
            text += f"   Осталось: {remaining}\n\n"
        
        await message.answer(text, parse_mode='Markdown')
        logger.info(f"Пользователь {message.from_user.id} запросил статистику")
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        await message.answer("❌ Произошла ошибка при расчёте статистики")

# Команда /admin
@dp.message(Command('admin'))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Доступ запрещен. Только для администраторов.")
        return
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📝 Установить пары")],
            [types.KeyboardButton(text="📋 Список предметов")],
            [types.KeyboardButton(text="🔄 Сбросить данные")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "🔑 **Панель администратора**\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    logger.info(f"Админ {message.from_user.id} открыл панель")

# Обработка кнопок админ-панели
@dp.message(F.text == "📝 Установить пары")
async def admin_set_subject(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    subjects_list = "\n".join([f"{code} — {name}" for code, name in DEFAULT_SUBJECTS.items()])

    await message.answer(
        f"📚 **Доступные предметы:**\n\n{subjects_list}\n\n"
        "Отправьте в формате:\n`код предмета` `количество пар`\n\n"
        "Пример: `EH.01 60`",
        parse_mode='Markdown'
    )

    await state.set_state(AdminState.waiting_for_hours)

@dp.message(AdminState.waiting_for_hours)
async def admin_save_subject(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer("❌ Неверный формат. Пример: МДК 01.01 60")
        return

    try:
        hours = int(parts[-1])
    except ValueError:
        await message.answer("❌ пары должны быть числом")
        return

    code = " ".join(parts[:-1]).upper().strip()

    if code not in DEFAULT_SUBJECTS:
        available = "\n".join(DEFAULT_SUBJECTS.keys())
        await message.answer(
            f"❌ Предмет {code} не найден\n\n"
            f"Доступные коды:\n{available}"
        )
        return

    db.set_subject_hours(code, DEFAULT_SUBJECTS[code], hours)
    await message.answer(f"✅ Установлено: {DEFAULT_SUBJECTS[code]} — {hours} часов")
    await state.clear()   # ← ВНУТРИ функции (с отступом!)

@dp.message(F.text == "📋 Список предметов")
async def admin_list_subjects(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    subjects = db.get_all_subjects()
    
    if not subjects:

        await message.answer("📭 Нет сохранённых предметов")
        return
    
    text = "📋 **Сохранённые предметы:**\n\n"
    for subject in subjects:
        text += f"{subject['code']} — {subject['name']}: {subject['total_hours']} ч.\n"
    
    await message.answer(text, parse_mode='Markdown')

@dp.message(F.text == "🔄 Сбросить данные")
async def admin_reset(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    db.reset_subjects()
    await message.answer("✅ Все данные сброшены")

# Команда /set_subject
@dp.message(Command('set_subject'))
async def cmd_set_subject(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Только для администраторов")
        return
    
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.answer("Используйте: /set_subject ЧАСЫ КОД\nПример: /set_subject 60 EH.01")
            return
        
        hours = int(args[1])
        code = args[2]
        
        if code not in DEFAULT_SUBJECTS:
            await message.answer(f"❌ Предмет {code} не найден")
            return
        
        db.set_subject_hours(code, DEFAULT_SUBJECTS[code], hours)
        await message.answer(f"✅ {DEFAULT_SUBJECTS[code]}: {hours} часов")
        
    except ValueError:
        await message.answer("❌ Часы должны быть числом")
    except Exception as e:
        logger.error(f"Ошибка /set_subject: {e}")
        await message.answer("❌ Произошла ошибка")

# Команда /subjects
@dp.message(Command('subjects'))
async def cmd_subjects(message: Message):
    subjects = db.get_all_subjects()
    
    if not subjects:
        await message.answer("📭 Нет сохранённых предметов")
        return
    
    text = "📋 **Предметы:**\n\n"
    for subject in subjects:
        text += f"{subject['code']} — {subject['name']}: {subject['total_hours']} ч.\n"
    
    await message.answer(text, parse_mode='Markdown')

# Команда /reset
@dp.message(Command('reset'))
async def cmd_reset(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Только для администраторов")
        return
    
    db.reset_subjects()
    await message.answer("✅ Все данные сброшены")
    logger.info(f"Админ {message.from_user.id} сбросил данные")

async def auto_update_schedule():
    while True:
        try:
            logger.info("🔄 Автообновление расписания...")

            today = date.today()
            lessons = parser.get_timetable(today)

            if lessons:
                logger.info(f"✅ Обновлено: {len(lessons)} пар")
            else:
                logger.warning("⚠️ Не удалось обновить расписание")

        except Exception as e:
            logger.error(f"❌ Ошибка автообновления: {e}")

        await asyncio.sleep(1800)  # каждые 30 минут

# Запуск бота
async def main():
    logger.info("Бот запускается...")

    # запускаем автообновление в фоне
    asyncio.create_task(auto_update_schedule())

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
