import sqlite3
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name: str = 'bot_data.db'):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                
                # Таблица предметов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subjects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        total_hours INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица кэша расписания
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS timetable_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        telegram_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    def add_user(self, telegram_id: int, username: str = None, 
                 first_name: str = None, last_name: str = None):
        """Добавление пользователя"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (telegram_id, username, first_name, last_name, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (telegram_id, username, first_name, last_name))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
    
    def set_subject_hours(self, code: str, name: str, hours: int):
        """Установка количества часов для предмета"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO subjects 
                    (code, name, total_hours, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (code, name, hours))
                conn.commit()
                logger.info(f"Предмет {code} обновлен: {hours} пар")
        except Exception as e:
            logger.error(f"Ошибка обновления предмета: {e}")
            raise
    
    def get_subject_hours(self, code: str) -> Optional[int]:
        """Получение количества часов для предмета"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT total_hours FROM subjects WHERE code = ?
                ''', (code,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка получения предмета: {e}")
            return None
    
    def get_all_subjects(self) -> List[Dict]:
        """Получение всех предметов"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM subjects ORDER BY code')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения предметов: {e}")
            return []
    
    def reset_subjects(self):
        """Сброс всех предметов"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM subjects')
                conn.commit()
                logger.info("Все предметы сброшены")
        except Exception as e:
            logger.error(f"Ошибка сброса предметов: {e}")
    
    def cache_timetable(self, date: str, content: str):
        """Кэширование расписания"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO timetable_cache 
                    (date, content, created_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (date, content))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка кэширования: {e}")
    
    def get_cached_timetable(self, date: str, ttl: int = 3600) -> Optional[str]:
        """Получение кэшированного расписания"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT content FROM timetable_cache 
                    WHERE date = ? 
                    AND (julianday('now') - julianday(created_at)) * 86400 < ?
                ''', (date, ttl))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка получения кэша: {e}")
            return None