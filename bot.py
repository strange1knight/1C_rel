import os
import logging
import json
import re
from pathlib import Path
from datetime import datetime
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import telebot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in .env")

# Настройка прокси для Telebot (если нужен)
TOR_PROXY = os.getenv("TOR_PROXY", "socks5://127.0.0.1:9150")
try:
    import telebot.apihelper
    telebot.apihelper.proxy = {'https': TOR_PROXY, 'http': TOR_PROXY}
except:
    pass

bot = telebot.TeleBot(BOT_TOKEN)

# Создаем сессию
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})

def load_cookies_from_file():
    """Загружает cookies из файла cookies.json"""
    cookie_file = Path("cookies.json")
    if not cookie_file.exists():
        print("cookies.json not found")
        return False
    
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            
            if isinstance(cookies, list):
                cookies_dict = {}
                for cookie in cookies:
                    if 'name' in cookie and 'value' in cookie:
                        cookies_dict[cookie['name']] = cookie['value']
                cookies = cookies_dict
            
            if isinstance(cookies, dict):
                for name, value in cookies.items():
                    if name and value:
                        if name == "userSettings" and value.startswith('"'):
                            value = value.strip('"')
                        session.cookies.set(name, value, domain="releases.1c.ru")
                print(f"Loaded {len(cookies)} cookies")
                return True
            else:
                return False
                
    except Exception as e:
        print(f"Error loading cookies: {e}")
        return False

def check_auth():
    """Проверяет, работает ли авторизация"""
    try:
        response = session.get("https://releases.1c.ru/total", timeout=30)
        if "loginForm" not in response.text and "Вход" not in response.text:
            return True
        return False
    except Exception as e:
        print(f"Auth check error: {e}")
        return False

# ================== ЛОГИРОВАНИЕ ДИАЛОГОВ ==================
class UserLog:
    _loggers = {}
    @classmethod
    def get_logger(cls, user_id: int):
        if user_id not in cls._loggers:
            Path("logs").mkdir(exist_ok=True)
            logger = logging.getLogger(f"user_{user_id}")
            logger.setLevel(logging.INFO)
            fh = logging.FileHandler(f"logs/{user_id}.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(Y-%m-%d %H:%M:%S - %(message)s"))
            logger.addHandler(fh)
            cls._loggers[user_id] = logger
        return cls._loggers[user_id]

# ================== КОНФИГУРАЦИЯ ==================
PRODUCTS = {
    "bp": {
        "name": "Бухгалтерия предприятия ПРОФ, редакция 3.0",
        "project_id": "Accounting30",
        "nick": "Accounting30"
    },
    "bp_corp": {
        "name": "Бухгалтерия предприятия КОРП, редакция 3.0",
        "project_id": "AccountingCorp30",
        "nick": "AccountingCorp30"
    },
    "zup": {
        "name": "Зарплата и управление персоналом ПРОФ, редакция 3",
        "project_id": "HRM30",
        "nick": "HRM30"
    },
    "zup_corp": {
        "name": "Зарплата и управление персоналом КОРП, редакция 3",
        "project_id": "HRMCorp30",
        "nick": "HRMCorp30"
    },
    "ut": {
        "name": "Управление торговлей, редакция 11",
        "project_id": "Trade110",
        "nick": "Trade110"
    }
}

def version_to_tuple(version_str):
    """Преобразует строку версии в кортеж для сравнения"""
    parts = re.findall(r'\d+', version_str)
    return tuple(int(p) for p in parts[:4])  # Берем первые 4 числа

def get_all_releases_for_product(product_key):
    """Получает ВСЕ релизы для продукта (для калькулятора обновлений)"""
    if product_key not in PRODUCTS:
        return None
        
    product = PRODUCTS[product_key]
    url = f"https://releases.1c.ru/project/{product['project_id']}"
    
    try:
        response = session.get(url, timeout=30)
        
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        
        if soup.find("form", {"id": "loginForm"}):
            return None

        table = soup.find("table", {"id": "versionsTable"})
        if not table:
            return None

        rows = table.find_all("tr")
        releases = []
        
        # Парсим все строки таблицы
        for row in rows[1:]:  # Пропускаем заголовок
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            
            version_link = cells[0].find("a")
            if not version_link:
                continue
            
            version = version_link.text.strip()
            date_text = cells[1].text.strip() if len(cells) > 1 else "Не указана"
            update_versions = cells[2].text.strip() if len(cells) > 2 else ""
            min_platform = cells[3].text.strip() if len(cells) > 3 else "Не указана"
            
            releases.append({
                "version": version,
                "date": date_text,
                "update_versions": update_versions,
                "min_platform": min_platform
            })
        
        return releases
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_latest_release(product_key):
    """Получает последний релиз с releases.1c.ru"""
    releases = get_all_releases_for_product(product_key)
    if releases and len(releases) > 0:
        return releases[0]
    return None

def calculate_update_path(product_key, current_version):
    """
    Рассчитывает путь обновления от текущей версии до последней
    Возвращает: dict с количеством обновлений и списком ключевых версий
    """
    releases = get_all_releases_for_product(product_key)
    if not releases:
        return {"error": "Не удалось получить список релизов"}
    
    # Получаем все версии в порядке от новых к старым (так как на сайте они отсортированы)
    all_versions = [r["version"] for r in releases]
    latest_version = all_versions[0]
    
    # Преобразуем текущую версию в кортеж для сравнения
    current_tuple = version_to_tuple(current_version)
    
    # Находим индекс текущей версии в списке (или ближайшей младшей)
    current_index = None
    for i, ver in enumerate(all_versions):
        if version_to_tuple(ver) == current_tuple:
            current_index = i
            break
    
    # Если точная версия не найдена, ищем ближайшую младшую
    if current_index is None:
        for i, ver in enumerate(all_versions):
            if version_to_tuple(ver) < current_tuple:
                current_index = i - 1 if i > 0 else 0
                break
    
    if current_index is None:
        return {"error": f"Версия {current_version} не найдена в списке релизов"}
    
    # Если текущая версия - последняя
    if current_index == 0:
        return {
            "is_latest": True,
            "current_version": current_version,
            "latest_version": latest_version,
            "message": "У вас установлена актуальная версия"
        }
    
    # Получаем версии, которые нужно установить для обновления
    updates_needed = all_versions[:current_index]  # от последней до версии перед текущей
    updates_needed.reverse()  # Разворачиваем в порядке от старой к новой
    
    # Выбираем ключевые версии (каждую 5-ю для длинных списков)
    total_updates = len(updates_needed)
    key_versions = []
    
    if total_updates <= 10:
        key_versions = updates_needed
    else:
        step = max(1, total_updates // 10)
        for i in range(0, total_updates, step):
            if updates_needed[i] not in key_versions:
                key_versions.append(updates_needed[i])
        if updates_needed[-1] not in key_versions:
            key_versions.append(updates_needed[-1])
    
    return {
        "is_latest": False,
        "current_version": current_version,
        "latest_version": latest_version,
        "total_updates": total_updates,
        "key_versions": key_versions
    }

def get_latest_releases_all():
    """Получает последние релизы для всех конфигураций"""
    results = {}
    for key in PRODUCTS:
        results[key] = get_latest_release(key)
        time.sleep(0.5)
    return results

def get_api_demo_data():
    """Демонстрация получения данных через HTTP API"""
    return {
        "status": "success",
        "source": "HTTP API Demo",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": [
            {"product": "Бухгалтерия предприятия", "version": "3.0.197.22", "date": "2026-05-10"},
            {"product": "Зарплата и управление персоналом", "version": "3.1.30.123", "date": "2026-02-15"},
            {"product": "Управление торговлей", "version": "11.5.20.67", "date": "2026-02-10"},
        ]
    }

# ================== ОБРАБОТЧИКИ КОМАНД ==================

# КОМАНДА 1: /start и /help - Приветствие и список команд
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger = UserLog.get_logger(user_id)
    logger.info(f"Пользователь {username} выполнил команду: {message.text}")
    
    help_text = """=== БОТ ДЛЯ ПРОВЕРКИ РЕЛИЗОВ 1С ===

Доступные команды:

1. /releases - Получить последние релизы всех конфигураций
   Механизм: скрапинг HTML с авторизацией через cookies

2. /check [конфигурация] - Проверить конкретную конфигурацию
   Механизм: скрапинг HTML с детальной информацией
   Пример: /check bp

3. /update [конфигурация] [версия] - Калькулятор обновлений
   Механизм: анализ списка релизов
   Пример: /update bp 3.0.150.25

4. /apidata - Получить данные через HTTP API
   Механизм: HTTP API запрос (демонстрация)

5. /history - Показать историю диалога
   Механизм: логирование в файл

Доступные конфигурации:
- bp - Бухгалтерия предприятия ПРОФ
- bp_corp - Бухгалтерия предприятия КОРП
- zup - Зарплата и управление персоналом ПРОФ
- zup_corp - Зарплата и управление персоналом КОРП
- ut - Управление торговлей

Примеры:
/check bp
/check zup
/update bp 3.0.150.25
/update zup 3.1.20.10"""
    
    bot.reply_to(message, help_text)
    logger.info(f"Бот отправил справку пользователю {username}")

# КОМАНДА 2: /releases - Получение всех релизов (скрапинг HTML)
@bot.message_handler(commands=['releases'])
def all_releases(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger = UserLog.get_logger(user_id)
    logger.info(f"Пользователь {username} выполнил команду: /releases")
    
    status_msg = bot.reply_to(message, "Выполняется скрапинг страниц релизов 1С...")
    
    if not check_auth():
        bot.edit_message_text(
            "Ошибка авторизации\n\n"
            "Не удалось получить доступ к порталу releases.1c.ru.\n"
            "Проверьте файл cookies.json или обновите cookies.",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        return
    
    results = []
    for key, product in PRODUCTS.items():
        release = get_latest_release(key)
        if release:
            results.append(
                f"Конфигурация: {product['name']}\n"
                f"  Версия: {release['version']}\n"
                f"  Дата выхода: {release['date']}\n"
                f"  Минимальная версия платформы: {release['min_platform']}\n"
            )
        else:
            results.append(f"Конфигурация: {product['name']} - данные не получены\n")
        time.sleep(0.5)
    
    response = "=== РЕЗУЛЬТАТЫ ПРОВЕРКИ РЕЛИЗОВ ===\n\n"
    response += "\n".join(results)
    response += "\n---\nМетод получения данных: скрапинг HTML с авторизацией через cookies"
    response += "\nИсточник: https://releases.1c.ru"
    
    bot.edit_message_text(response, chat_id=message.chat.id, message_id=status_msg.message_id)
    logger.info(f"Бот отправил результаты релизов пользователю {username}")

# КОМАНДА 3: /check - Проверка конкретной конфигурации (скрапинг HTML)
@bot.message_handler(commands=['check'])
def check_release(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger = UserLog.get_logger(user_id)
    
    args = message.text.split()
    if len(args) < 2:
        response = "Использование: /check [конфигурация]\nДоступные: bp, bp_corp, zup, zup_corp, ut\nПример: /check bp"
        bot.reply_to(message, response)
        logger.info(f"Пользователь {username} ввел команду /check без аргументов")
        return
        
    product_key = args[1].lower()
    if product_key not in PRODUCTS:
        response = f"Неизвестная конфигурация: {product_key}\nДоступные: bp, bp_corp, zup, zup_corp, ut"
        bot.reply_to(message, response)
        logger.info(f"Пользователь {username} указал неизвестную конфигурацию: {product_key}")
        return
    
    product = PRODUCTS[product_key]
    logger.info(f"Пользователь {username} выполнил команду: /check {product_key}")
    
    status_msg = bot.reply_to(message, f"Выполняется проверка конфигурации {product['name']}...")
    
    if not check_auth():
        bot.edit_message_text(
            "Ошибка авторизации\n\nНе удалось получить доступ к порталу releases.1c.ru.",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        return
        
    release = get_latest_release(product_key)
    
    if release:
        response = f"=== КОНФИГУРАЦИЯ: {product['name']} ===\n\n"
        response += f"Актуальная версия: {release['version']}\n"
        response += f"Дата выпуска: {release['date']}\n"
        response += f"Минимальная версия платформы: {release['min_platform']}\n\n"
        
        # Добавляем информацию о версиях для обновления (если есть и не слишком длинная)
        if release.get('update_versions') and release['update_versions'] != "Не указаны" and release['update_versions']:
            update_versions = release['update_versions']
            if len(update_versions) > 100:
                update_versions = update_versions[:100] + "..."
            response += f"Обновление возможно с версий:\n{update_versions}\n\n"
        
        response += f"Ссылка для скачивания:\nhttps://releases.1c.ru/version_files?nick={product['nick']}&ver={release['version']}\n\n"
        response += "---\nМетод получения данных: скрапинг HTML с авторизацией через cookies"
    else:
        response = f"Не удалось получить данные для конфигурации {product['name']}"
    
    bot.edit_message_text(response, chat_id=message.chat.id, message_id=status_msg.message_id)
    logger.info(f"Бот отправил информацию о релизе {product_key} пользователю {username}")

# КОМАНДА 4: /update - Калькулятор обновлений
@bot.message_handler(commands=['update'])
def update_calculator(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger = UserLog.get_logger(user_id)
    
    args = message.text.split()
    if len(args) < 3:
        response = "Использование: /update [конфигурация] [версия]\n"
        response += "Пример: /update bp 3.0.150.25\n"
        response += "Доступные конфигурации: bp, bp_corp, zup, zup_corp, ut"
        bot.reply_to(message, response)
        logger.info(f"Пользователь {username} ввел команду /update с недостаточными аргументами")
        return
        
    product_key = args[1].lower()
    current_version = args[2]
    
    if product_key not in PRODUCTS:
        response = f"Неизвестная конфигурация: {product_key}\nДоступные: bp, bp_corp, zup, zup_corp, ut"
        bot.reply_to(message, response)
        return
    
    # Проверка формата версии
    version_pattern = re.compile(r'^\d+\.\d+\.\d+\.\d+$')
    if not version_pattern.match(current_version):
        response = f"Неверный формат версии: {current_version}\n"
        response += "Версия должна быть в формате: X.X.X.X (например, 3.0.150.25)"
        bot.reply_to(message, response)
        return
    
    product = PRODUCTS[product_key]
    logger.info(f"Пользователь {username} выполнил команду: /update {product_key} {current_version}")
    
    status_msg = bot.reply_to(message, f"Анализирую путь обновления для {product['name']} с версии {current_version}...")
    
    if not check_auth():
        bot.edit_message_text(
            "Ошибка авторизации\n\nНе удалось получить доступ к порталу releases.1c.ru.",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        return
    
    # Получаем список всех релизов
    all_releases = get_all_releases_for_product(product_key)
    if not all_releases:
        bot.edit_message_text(
            f"Не удалось получить список релизов для {product['name']}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        return
    
    # Рассчитываем путь обновления
    update_info = calculate_update_path(product_key, current_version)
    
    if "error" in update_info:
        bot.edit_message_text(
            f"Ошибка: {update_info['error']}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        return
    
    if update_info.get("is_latest"):
        response = f"=== КАЛЬКУЛЯТОР ОБНОВЛЕНИЙ ===\n\n"
        response += f"Конфигурация: {product['name']}\n"
        response += f"Ваша версия: {current_version}\n"
        response += f"Актуальная версия: {update_info['latest_version']}\n\n"
        response += f"Результат: {update_info['message']}\n\n"
        response += "---\nМетод получения данных: анализ списка релизов"
    else:
        response = f"=== КАЛЬКУЛЯТОР ОБНОВЛЕНИЙ ===\n\n"
        response += f"Конфигурация: {product['name']}\n"
        response += f"Ваша версия: {current_version}\n"
        response += f"Актуальная версия: {update_info['latest_version']}\n\n"
        response += f"Количество необходимых обновлений: {update_info['total_updates']}\n\n"
        
        if update_info['key_versions']:
            response += "Ключевые версии для обновления:\n"
            for ver in update_info['key_versions'][:15]:  # Не более 15 версий
                response += f"  - {ver}\n"
        
        response += "\n---\nМетод получения данных: анализ списка релизов"
    
    bot.edit_message_text(response, chat_id=message.chat.id, message_id=status_msg.message_id)
    logger.info(f"Бот отправил калькуляцию обновлений пользователю {username}: {update_info.get('total_updates', 0)} обновлений")

# КОМАНДА 5: /apidata - Получение данных через HTTP API (демонстрация)
@bot.message_handler(commands=['apidata'])
def api_demo(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger = UserLog.get_logger(user_id)
    logger.info(f"Пользователь {username} выполнил команду: /apidata")
    
    api_data = get_api_demo_data()
    
    response = "=== ОТВЕТ HTTP API ===\n\n"
    response += f"Статус: {api_data['status']}\n"
    response += f"Источник: {api_data['source']}\n"
    response += f"Время запроса: {api_data['timestamp']}\n\n"
    response += "Полученные данные:\n"
    
    for item in api_data['data']:
        response += f"- {item['product']}: версия {item['version']} ({item['date']})\n"
    
    response += "\n---\nМетод получения данных: HTTP API запрос"
    
    bot.reply_to(message, response)
    logger.info(f"Бот отправил демонстрационные API данные пользователю {username}")

# КОМАНДА 6: /history - Показать историю диалога (логирование в файл)
@bot.message_handler(commands=['history'])
def show_history(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger = UserLog.get_logger(user_id)
    logger.info(f"Пользователь {username} выполнил команду: /history")
    
    log_file = Path(f"logs/{user_id}.log")
    
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-30:] if len(lines) > 30 else lines
            history = ''.join(last_lines)
        
        response = f"=== ИСТОРИЯ ДИАЛОГА ===\n\n"
        response += f"Файл: {user_id}.log\n"
        response += f"Всего записей: {len(lines)}\n"
        response += f"Показано последних: {len(last_lines)}\n\n"
        response += f"{history}\n"
        response += "---\nМетод получения данных: чтение из файловой системы"
        
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                bot.send_message(message.chat.id, response[i:i+4000])
        else:
            bot.reply_to(message, response)
    else:
        response = "История диалога пуста.\nОтправьте несколько команд, чтобы заполнить историю."
        bot.reply_to(message, response)
    
    logger.info(f"Бот отправил историю диалога пользователю {username}")

# Обработка неизвестных команд
@bot.message_handler(func=lambda message: True)
def unknown(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger = UserLog.get_logger(user_id)
    logger.info(f"Пользователь {username} ввел неизвестную команду: {message.text}")
    
    response = "Неизвестная команда. Используйте /help для просмотра доступных команд."
    bot.reply_to(message, response)

# ================== ЗАПУСК БОТА ==================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("БОТ ДЛЯ ПРОВЕРКИ РЕЛИЗОВ 1С")
    print("=" * 60)
    
    # Загрузка cookies
    if load_cookies_from_file():
        print("Файл cookies.json загружен успешно")
        if check_auth():
            print("Авторизация на портале 1С подтверждена")
        else:
            print("ВНИМАНИЕ: Cookies могли устареть. Обновите cookies.json")
    else:
        print("ОШИБКА: Не удалось загрузить файл cookies.json")
        print("Создайте файл cookies.json в папке с ботом")
    
    print("\n" + "=" * 60)
    print("БОТ ЗАПУЩЕН")
    print("Доступные команды:")
    print("  /start, /help - справка")
    print("  /releases - все релизы")
    print("  /check [конфиг] - проверка конфигурации")
    print("  /update [конфиг] [версия] - калькулятор обновлений")
    print("  /apidata - API демонстрация")
    print("  /history - история диалога")
    print("=" * 60 + "\n")
    
    try:
        bot.infinity_polling(timeout=60)
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка: {e}")