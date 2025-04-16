import os
import time
import requests
import socket
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib3.exceptions import ReadTimeoutError

# Устанавливаем переменную окружения DISPLAY для использования Xvfb
os.environ["DISPLAY"] = ":99"  # Указывает на виртуальный дисплей

# Настройки Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")  # Запуск без интерфейса
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")  # Исправляет проблемы с памятью в Linux
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-infobars")
# Добавляем user-agent, чтобы снизить вероятность блокировки
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
chrome_options.page_load_strategy = 'eager'  # Загружать только необходимое

# Файл с сохранённой информацией
data_file = "model_info.txt"

# Telegram
bot_token = "6858480572:AAGUJwUq_UevIhrbQS6cG2nN0hfyDw8yh54"
chat_id = "-4134676016"

# Константы
MAX_RETRIES = 3
PAGE_LOAD_TIMEOUT = 60  # Максимальное время загрузки страницы в секундах
ELEMENT_WAIT_TIMEOUT = 20  # Максимальное время ожидания элементов
SCROLL_TIMEOUT = 15  # Максимальное время на прокрутку в секундах
BETWEEN_CHECKS_INTERVAL = 600  # Пауза между проверками (10 минут)
ERROR_RETRY_INTERVAL = 600  # Пауза после ошибок (10 минут)
DRIVER_MAX_LIFETIME = 7200  # Максимальное время жизни драйвера (2 часа) перед принудительным перезапуском

# Проверка доступности сайта перед запуском Selenium
def check_site_availability(url, timeout=10):
    try:
        domain = url.split("//")[-1].split("/")[0]
        socket.gethostbyname(domain)
        response = requests.head(url, timeout=timeout)
        return True
    except Exception:
        return False

# Инициализация драйвера с защитой от сбоев
def init_driver():
    for attempt in range(MAX_RETRIES):
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            driver.implicitly_wait(10)  # Умеренное глобальное ожидание
            return driver
        except Exception:
            time.sleep(5)
    
    # Если все попытки не удались
    send_telegram_message("⚠️ Ошибка: Не удалось запустить WebDriver после нескольких попыток", bot_token, chat_id)
    return None  # Явно возвращаем None вместо возбуждения исключения

# Безопасное закрытие драйвера
def safe_quit_driver(driver):
    if driver:
        try:
            driver.quit()
        except Exception:
            pass
    return None

# Функция ожидания появления хотя бы одного элемента
def wait_for_products(driver, timeout=ELEMENT_WAIT_TIMEOUT):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-block-info-wrapper"))
        )
        return True
    except TimeoutException:
        return False
    except Exception:
        return False

# Чтение данных из файла с обработкой ошибок
def read_file():
    try:
        if not os.path.exists(data_file):
            return set()
            
        with open(data_file, "r", encoding="utf-8") as f:
            content = f.readlines()
        return set(line.strip() for line in content)
    except FileNotFoundError:
        return set()
    except Exception:
        return set()

# Отправка сообщений в Telegram
def send_telegram_message(message, bot_token, chat_id, retry=2):
    # Максимальная длина сообщения в Telegram - 4096 символов
    MAX_MESSAGE_LENGTH = 4000  # Берем с запасом
    
    # Если сообщение слишком длинное, разбиваем на части
    if len(message) > MAX_MESSAGE_LENGTH:
        chunks = []
        
        # Если есть перечисление моделей, разбиваем по строкам
        if "\n" in message:
            lines = message.split("\n")
            current_chunk = ""
            
            for line in lines:
                # Если добавление новой строки сделает чанк слишком длинным
                if len(current_chunk + "\n" + line) > MAX_MESSAGE_LENGTH:
                    if current_chunk:  # Добавляем текущий чанк, если он не пустой
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:  # Если строка сама по себе слишком длинная
                        if len(line) > MAX_MESSAGE_LENGTH:
                            # Разбиваем длинную строку на части
                            for i in range(0, len(line), MAX_MESSAGE_LENGTH):
                                chunks.append(line[i:i+MAX_MESSAGE_LENGTH])
                        else:
                            chunks.append(line)
                else:
                    if current_chunk:
                        current_chunk += "\n" + line
                    else:
                        current_chunk = line
            
            # Добавляем последний чанк, если он не пустой
            if current_chunk:
                chunks.append(current_chunk)
        else:
            # Если нет переносов строк, просто разбиваем по символам
            for i in range(0, len(message), MAX_MESSAGE_LENGTH):
                chunks.append(message[i:i+MAX_MESSAGE_LENGTH])
        
        # Отправляем каждый чанк отдельным сообщением
        success = True
        for i, chunk in enumerate(chunks):
            chunk_message = f"Часть {i+1}/{len(chunks)}: {chunk}" if len(chunks) > 1 else chunk
            if not _send_telegram_message(chunk_message, bot_token, chat_id, retry):
                success = False
        return success
    else:
        # Сообщение достаточно короткое, отправляем как есть
        return _send_telegram_message(message, bot_token, chat_id, retry)

# Внутренняя функция для фактической отправки сообщения
def _send_telegram_message(message, bot_token, chat_id, retry=2):
    for attempt in range(retry + 1):
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            params = {
                "chat_id": chat_id,
                "text": message,
            }
            response = requests.get(url, params=params, timeout=30)
            result = response.json()
            if not result.get('ok'):
                return False
            return True
        except Exception:
            if attempt < retry:
                time.sleep(5)
    return False

# Безопасная прокрутка страницы с таймаутом
def safe_scroll(driver, max_scroll_time=SCROLL_TIMEOUT):
    scroll_start_time = time.time()
    scroll_pause_time = 1
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Проверка на превышение времени прокрутки
        if time.time() - scroll_start_time > max_scroll_time:
            break
            
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        except Exception:
            break

# URL страницы
url = "https://www.houseofmodelcars.com/eng/collection/formula-1/6?limit=192&sort=price&direction=asc&m=9+19+47+48+10+1+2&s=13&y=2024+2023+2022+2021+2020+2019+2018+2017+2007+2006+2001+2000"

# Основной цикл выполнения с защитой от сбоев
def main():
    driver = None
    driver_start_time = 0
    
    try:
        driver = init_driver()
        # Проверка, что драйвер успешно инициализирован
        if driver is None:
            send_telegram_message("⚠️ Критическая ошибка: Не удалось инициализировать WebDriver", bot_token, chat_id)
            time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед новой попыткой
            return  # Завершаем выполнение, если драйвер не инициализирован
            
        driver_start_time = time.time()
        error_counter = 0
        
        while True:
            try:
                # Проверка драйвера перед использованием
                if driver is None:
                    driver = init_driver()
                    if driver is None:
                        # Если снова не удалось инициализировать, делаем паузу и продолжаем
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    
                # Проверяем, не пора ли перезапустить драйвер из-за превышения времени жизни
                current_time = time.time()
                if current_time - driver_start_time > DRIVER_MAX_LIFETIME:
                    # Перезапускаем драйвер каждые DRIVER_MAX_LIFETIME секунд для предотвращения утечек памяти
                    driver = safe_quit_driver(driver)
                    driver = init_driver()
                    if driver is None:
                        # Если не удалось инициализировать, делаем паузу и продолжаем
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    error_counter = 0
                
                # Проверка доступности сайта перед запуском Selenium
                if not check_site_availability(url):
                    time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед повторной попыткой
                    continue
                
                previous_items = read_file()
                
                try:
                    # Проверка драйвера перед вызовом get()
                    if driver is None:
                        driver = init_driver()
                        if driver is None:
                            time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                            continue
                        driver_start_time = time.time()
                        
                    driver.get(url)
                except TimeoutException:
                    # Перезапускаем драйвер при таймауте
                    driver = safe_quit_driver(driver)
                    driver = init_driver()
                    if driver is None:
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    continue
                except Exception as e:
                    # Проверяем на ошибку ReadTimeoutError
                    if "Read timed out" in str(e) or isinstance(e.__cause__, ReadTimeoutError):
                        # Перезапуск драйвера при таймауте чтения
                        driver = safe_quit_driver(driver)
                        driver = init_driver()
                        if driver is None:
                            time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                            continue
                        driver_start_time = time.time()
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    raise  # Пробрасываем другие исключения
                
                # Проверка драйвера перед вызовом wait_for_products
                if driver is None:
                    driver = init_driver()
                    if driver is None:
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    continue
                    
                # Проверяем загрузку элементов
                if not wait_for_products(driver):
                    error_counter += 1
                    if error_counter >= 3:
                        # Перезапуск драйвера после нескольких ошибок
                        driver = safe_quit_driver(driver)
                        driver = init_driver()
                        if driver is None:
                            time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                            continue
                        driver_start_time = time.time()
                        error_counter = 0
                    time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед следующей попыткой
                    continue
                
                # Сбрасываем счетчик ошибок при успешной загрузке
                error_counter = 0
                
                # Проверка драйвера перед вызовом safe_scroll
                if driver is None:
                    driver = init_driver()
                    if driver is None:
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    continue
                    
                # Скроллим страницу с безопасным таймаутом
                safe_scroll(driver)
                
                # Проверка драйвера перед получением товаров
                if driver is None:
                    driver = init_driver()
                    if driver is None:
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    continue
                
                # Получаем товары
                products = driver.find_elements(By.CLASS_NAME, "col-12.col-sm-6.col-md-6.col-lg-4.col-xl-3")
                if not products:
                    time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед следующей попыткой при отсутствии товаров
                    continue

                current_items = set()

                for product in products:
                    try:
                        info_tag = product.find_element(By.CLASS_NAME, "product-block-info-wrapper")
                        info = " ".join(info_tag.text.strip().split()).replace("Details »", "").strip()
                        current_items.add(info)
                    except Exception:
                        continue

                # Сравнение
                new_models = current_items - previous_items
                ended_models = previous_items - current_items

                message = ""

                if new_models or ended_models:
                    if new_models:
                        message += "\n🔥 Новые модели в Голландии:\n"
                        for item in sorted(new_models):
                            message += f"+ {item}\n"

                    if ended_models:
                        message += "\n❌ Закончились модели в Голландии:\n"
                        for item in sorted(ended_models):
                            message += f"- {item}\n"
                else:
                    message = "Изменений нет в Голландии."

                # Отправка сообщения
                if message:
                    send_telegram_message(message, bot_token, chat_id)

                # Обновляем файл, только если успешно получили товары
                if current_items:
                    try:
                        with open(data_file, "w", encoding="utf-8") as f:
                            for item in sorted(current_items):
                                f.write(item + "\n")
                    except Exception:
                        pass

                # Пауза между проверками (10 минут)
                time.sleep(BETWEEN_CHECKS_INTERVAL)
                
            except WebDriverException as e:
                # Проверяем на ошибку таймаута
                if "Read timed out" in str(e) or isinstance(e.__cause__, ReadTimeoutError):
                    driver = safe_quit_driver(driver)
                    driver = init_driver()
                    if driver is None:
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед повторной попыткой
                else:
                    # Перезапускаем драйвер при других проблемах WebDriver
                    driver = safe_quit_driver(driver)
                    driver = init_driver()
                    if driver is None:
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед повторной попыткой
                continue
                
            except Exception as e:
                # Проверяем на ошибку таймаута в любых других исключениях
                if "Read timed out" in str(e):
                    driver = safe_quit_driver(driver)
                    driver = init_driver()
                    if driver is None:
                        time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут
                        continue
                    driver_start_time = time.time()
                    time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед повторной попыткой
                    continue
                
                # Отправляем уведомление об ошибке
                send_telegram_message(f"⚠️ Ошибка в работе бота: {e}", bot_token, chat_id)
                time.sleep(ERROR_RETRY_INTERVAL)  # Ждем 10 минут перед повторной попыткой

    except KeyboardInterrupt:
        pass
    except Exception as e:
        send_telegram_message(f"❌ Критическая ошибка: {e}", bot_token, chat_id)
    finally:
        safe_quit_driver(driver)

if __name__ == "__main__":
    main()