import win32gui
import win32con
import pyautogui
import time
import os
import subprocess
import keyboard
import pyperclip
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram_bot import TwitterTelegramBot
from datetime import datetime

processed_hwnds = set()
notification_queue = []
processed_tweet_ids = set()  # Хранение обработанных ID твитов

# Twitter API configuration
TWITTER_API_KEY = "ff517b33a69d4f9e92e4d3ed8d74d84d"
TWITTER_API_URL = "https://api.twitterapi.io/twitter/tweets"

# Telegram configuration
TELEGRAM_BOT_TOKEN = "7629741730:AAG2ACQnz7rKjbEIVacxN0MoL9MhD4d7g_I"  # Replace with your bot token
TELEGRAM_CHAT_ID = -1002441630375  # Replace with your chat ID

# Discord configuration
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1359236110571540540/FrXkkYMmpLCSabDxbO0ku5vK0LeiPZ-kWVmH1TyUukEh4Spa1HXi9OTk7n6m4FwTkg45"  # Replace with your Discord webhook URL

# Initialize Telegram bot
telegram_bot = TwitterTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL)

def log_message(message):
    """Логирование сообщений с временной меткой"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    # Также можно добавить запись в файл, если нужно
    # with open('browser_monitor.log', 'a') as f:
    #     f.write(f"[{timestamp}] {message}\n")

def fetch_tweet_content(tweet_id):
    """Fetch tweet content using Twitter API"""
    try:
        # Проверяем, обрабатывали ли мы уже этот ID
        if tweet_id in processed_tweet_ids:
            print(f"Твит {tweet_id} уже был обработан ранее")
            return None
            
        headers = {
            "X-API-Key": TWITTER_API_KEY
        }
        params = {
            "tweet_ids": tweet_id
        }
        print(f"Запрашиваем данные для твита {tweet_id}")
        response = requests.get(TWITTER_API_URL, headers=headers, params=params)
        if response.status_code == 200:
            # Добавляем ID в список обработанных
            processed_tweet_ids.add(tweet_id)
            content = response.json()
            return content
        else:
            print(f"Error fetching tweet {tweet_id}: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"Exception while fetching tweet {tweet_id}: {e}")
        return None

def save_tweet_content(tweet_id, content):
    """Save tweet content to api.json and process it"""
    if not content:
        print("No content received from API")
        return False
    
    print("Received API response:", content)  # Debug log
    
    # Save to api.json
    with open('api.json', 'w', encoding='utf-8') as f:
        json.dump([content], f, ensure_ascii=False, indent=2)
    
    print("Saved content to api.json")  # Debug log
    
    # Process and send to Telegram
    telegram_bot.process_api_json()
    
    print(f"Processed tweet: {tweet_id}")
    return True

def find_main_browser_window():
    def callback(hwnd, windows):
        if win32gui.GetClassName(hwnd) == "YandexBrowser_WidgetWin_1":
            # Проверяем, что это не окно уведомления
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width > 500 and height > 300:  # Главное окно браузера обычно больше
                windows.append(hwnd)
        return True
    
    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows[0] if windows else None

def enum_windows_callback(hwnd, results):
    window_class = win32gui.GetClassName(hwnd)
    window_text = win32gui.GetWindowText(hwnd)
    
    if window_class == "YandexBrowser_WidgetWin_1" and hwnd not in processed_hwnds and hwnd not in [item[0] for item in notification_queue]:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        screen_width, screen_height = pyautogui.size()
        
        if (width > 0 and height > 0 and width < 500 and height < 300 and
            right > screen_width - 400 and bottom > screen_height - 400):
            results.append((hwnd, window_text, (left, top, right, bottom)))

def save_url_to_json(url):
    # Проверяем наличие и валидность URL
    if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
        print(f"Невалидный URL: {url}")
        return False
    
    # Выводим полученный URL для отладки
    print(f"Получен URL: {url}")
    
    # Извлекаем ID из URL для x.com/twitter.com ссылок
    tweet_id = None
    if 'x.com' in url or 'twitter.com' in url:
        parts = url.split('status/')
        if len(parts) > 1:
            tweet_id = parts[1].split('?')[0].split('/')[0]
            if not tweet_id.isdigit():
                print(f"Невалидный ID твита: {tweet_id}")
                return False
            else:
                print(f"Извлечен ID твита: {tweet_id}")
    else:
        print("URL не содержит ссылки на твит")
        return False
    
    # Проверяем, обрабатывали ли мы уже этот ID
    if tweet_id in processed_tweet_ids:
        print(f"Твит {tweet_id} уже был обработан ранее")
        return True
    
    # Если есть tweet_id, получаем и сохраняем контент
    if tweet_id:
        content = fetch_tweet_content(tweet_id)
        if content:
            return save_tweet_content(tweet_id, content)
    
    return False

def open_notification_and_parse(hwnd, title, rect):
    left, top, right, bottom = rect
    x = (left + right) // 2
    y = (top + bottom) // 2
    print(f"Текст: {title}")
    print(f"Координаты окна: {left}, {top}, {right}, {bottom}")
    print(f"Клик по: ({x}, {y})")
    
    # Проверяем, что окно все еще существует
    if not win32gui.IsWindow(hwnd):
        print(f"Окно {hwnd} больше не существует")
        processed_hwnds.add(hwnd)
        return False
    
    # Проверяем, что окно все еще видимо
    if not win32gui.IsWindowVisible(hwnd):
        print(f"Окно {hwnd} больше не видимо")
        processed_hwnds.add(hwnd)
        return False
    
    # Кликаем по уведомлению
    pyautogui.click(x, y)
    processed_hwnds.add(hwnd)
    
    # Ждём дольше для полной загрузки страницы
    time.sleep(0.15)  # Увеличиваем время ожидания
    
    try:
        # Находим главное окно браузера
        main_window = find_main_browser_window()
        if not main_window:
            raise Exception("Не удалось найти главное окно браузера")
        
        # Активируем окно браузера
        win32gui.SetForegroundWindow(main_window)
        time.sleep(0.1)  # Даем больше времени для активации окна
        
        # Копируем URL из адресной строки (нажимаем дважды для надежности)
        keyboard.press_and_release('alt+d')
        time.sleep(0.1)  # Даем больше времени для выделения адресной строки
        keyboard.press_and_release('ctrl+c')
        time.sleep(0.1)  # Даем больше времени для копирования
        
        # Проверяем, что URL скопировался
        url = pyperclip.paste()
        if not url or not url.startswith('http'):
            # Вторая попытка
            print("Первая попытка копирования URL не удалась, повторяем...")
            keyboard.press_and_release('alt+d')
            time.sleep(0.1)
            keyboard.press_and_release('ctrl+c')
            time.sleep(0.1)
            url = pyperclip.paste()
        
        # Сохраняем URL в JSON файл
        result = save_url_to_json(url)
        
        # Закрываем вкладку
        keyboard.press_and_release('ctrl+w')
        
        # Возвращаем результат обработки
        return result
        
    except Exception as e:
        print(f"Ошибка при получении URL: {e}")
        return False

def process_notification_queue():
    """Обрабатывает очередь уведомлений"""
    if not notification_queue:
        return
    
    # Берем первое уведомление из очереди
    hwnd, title, rect = notification_queue[0]
    
    # Обрабатываем уведомление
    result = open_notification_and_parse(hwnd, title, rect)
    
    # Удаляем уведомление из очереди
    notification_queue.pop(0)
    
    # Даем паузу перед обработкой следующего уведомления
    time.sleep(0.1)  # Увеличиваем паузу

def is_yandex_running():
    """Проверяет, запущен ли Яндекс браузер"""
    try:
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                class_name = win32gui.GetClassName(hwnd)
                if 'YandexBrowser_WidgetWin_1' in class_name:
                    windows.append(hwnd)
            return True

        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        return len(windows) > 0
    except Exception as e:
        log_message(f"Ошибка при проверке состояния браузера: {e}")
        return False

def restart_yandex():
    """Перезапускает Яндекс браузер"""
    try:
        log_message("Начинаем перезапуск Яндекс браузера...")
        
        # Закрываем все процессы Яндекс браузера
        log_message("Закрываем процессы Яндекс браузера...")
        os.system("taskkill /f /im yandex.exe")
        time.sleep(2)  # Даем время на закрытие
        
        # Проверяем, что все процессы закрыты
        if is_yandex_running():
            log_message("Не удалось закрыть браузер, пробуем еще раз...")
            os.system("taskkill /f /im yandex.exe /t")  # Закрываем все дочерние процессы
            time.sleep(2)
        
        # Запускаем Яндекс браузер
        log_message("Запускаем Яндекс браузер...")
        browser_path = "C:\\Users\\Administrator\\Desktop\\Yandex\\YandexBrowser\\Application\\browser.exe"
        if not os.path.exists(browser_path):
            log_message(f"Ошибка: браузер не найден по пути {browser_path}")
            return False
            
        subprocess.Popen([browser_path])
        time.sleep(5)  # Даем время на запуск
        
        # Проверяем, что браузер запустился
        if is_yandex_running():
            log_message("Яндекс браузер успешно перезапущен")
            return True
        else:
            log_message("Ошибка: браузер не запустился после перезапуска")
            return False
            
    except Exception as e:
        log_message(f"Критическая ошибка при перезапуске браузера: {e}")
        return False

def monitor_notifications():
    log_message("Мониторинг уведомлений от Яндекс.Браузера запущен...")
    log_message("Нажмите Ctrl+C для выхода")
    
    # Загружаем ранее обработанные ID, если есть
    global processed_tweet_ids
    try:
        if os.path.exists('processed_ids.json'):
            with open('processed_ids.json', 'r') as f:
                processed_tweet_ids = set(json.load(f))
            log_message(f"Загружено {len(processed_tweet_ids)} ранее обработанных ID твитов")
    except Exception as e:
        log_message(f"Ошибка при загрузке обработанных ID: {e}")
        processed_tweet_ids = set()
    
    # Проверяем начальное состояние браузера
    if not is_yandex_running():
        log_message("Яндекс браузер не запущен, выполняем начальный запуск...")
        if not restart_yandex():
            log_message("Не удалось запустить браузер, завершаем работу")
            return
    
    last_browser_check = time.time()
    browser_check_interval = 1  # Проверяем состояние браузера каждую секунду
    
    try:
        while True:
            current_time = time.time()
            
            # Проверяем состояние браузера каждую секунду
            if current_time - last_browser_check >= browser_check_interval:
                if not is_yandex_running():
                    log_message("Яндекс браузер не обнаружен, выполняем перезапуск...")
                    if not restart_yandex():
                        log_message("Не удалось перезапустить браузер, пробуем еще раз через 5 секунд...")
                        time.sleep(5)
                        continue
                last_browser_check = current_time
            
            try:
                # Находим новые уведомления и добавляем их в очередь
                new_notifications = []
                win32gui.EnumWindows(enum_windows_callback, new_notifications)
                
                for notification in new_notifications:
                    notification_queue.append(notification)
                    log_message(f"Добавлено новое уведомление в очередь: {notification[1]}")
                
                # Обрабатываем очередь уведомлений
                if notification_queue:
                    process_notification_queue()
                else:
                    # Если очередь пуста, делаем небольшую паузу
                    time.sleep(0.1)
                    
            except Exception as e:
                log_message(f"Ошибка в цикле мониторинга: {e}")
                time.sleep(0.1)
    except KeyboardInterrupt:
        log_message("Мониторинг остановлен пользователем")
    finally:
        # Сохраняем обработанные ID при выходе
        try:
            with open('processed_ids.json', 'w') as f:
                json.dump(list(processed_tweet_ids), f)
            log_message(f"Сохранено {len(processed_tweet_ids)} обработанных ID твитов")
        except Exception as e:
            log_message(f"Ошибка при сохранении обработанных ID: {e}")

if __name__ == "__main__":
    monitor_notifications()
