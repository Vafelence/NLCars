import os
import time
import requests
import logging
import socket
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Устанавливаем переменную окружения DISPLAY для использования Xvfb
os.environ["DISPLAY"] = ":99"  # Указывает на виртуальный дисплей

# Настройки Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")  # Запуск без интерфейса
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage") # Исправляет проблемы с памятью в Linux
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-infobars")
# Добавляем user-agent, чтобы снизить вероятность блокировки
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
chrome_options.page_load_strategy = 'eager' # Загружать только необходимое

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

# Проверка доступности сайта перед запуском Selenium
def check_site_availability(url, timeout=10):
    try:
        domain = url.split("//")[-1].split("/")[0]
        logger.info(f"Проверка доступности домена {domain}")
        socket.gethostbyname(domain)
        response = requests.head(url, timeout=timeout)
        logger.info(f"Сайт доступен, код ответа: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Сайт недоступен: {e}")
        return False

# Инициализация драйвера с защитой от сбоев
def init_driver():
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Попытка {attempt + 1} запуска WebDriver с опциями: {chrome_options.arguments}")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            driver.implicitly_wait(10)  # Умеренное глобальное ожидание
            return driver
        except Exception as e:
            logger.error(f"Ошибка при инициализации WebDriver (попытка {attempt + 1}): {e}")
            time.sleep(5)
    
    # Если все попытки не удались
    logger.critical("Не удалось инициализировать WebDriver после нескольких попыток")
    send_telegram_message("⚠️ Ошибка: Не удалось запустить WebDriver после нескольких попыток", bot_token, chat_id)
    raise RuntimeError("Не удалось инициализировать WebDriver")

# Функция ожидания появления хотя бы одного элемента
def wait_for_products(driver, timeout=ELEMENT_WAIT_TIMEOUT):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-block-info-wrapper"))
        )
        logger.info("Элементы на странице загружены.")
        return True
    except TimeoutException:
        logger.error(f"Таймаут при ожидании элементов на странице (превышено {timeout} секунд)")
        return False
    except Exception as e:
        logger.error(f"Ошибка при ожидании элементов на странице: {e}")
        return False

# Чтение данных из файла с обработкой ошибок
def read_file():
    try:
        logger.info(f"Начало чтения данных из файла {data_file}")
        start_time = time.time()  # Засекаем время
        if not os.path.exists(data_file):
            logger.warning("Файл с данными не найден, создается новый.")
            return set()
            
        with open(data_file, "r", encoding="utf-8") as f:
            content = f.readlines()
        logger.info(f"Чтение файла завершено за {time.time() - start_time:.2f} секунд")
        return set(line.strip() for line in content)
    except FileNotFoundError:
        logger.warning("Файл с данными не найден, создается новый.")
        return set()
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {data_file}: {e}")
        return set()

# Отправка сообщений в Telegram
def send_telegram_message(message, bot_token, chat_id, retry=2):
    for attempt in range(retry + 1):
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            params = {
                "chat_id": chat_id,
                "text": message,
            }
            response = requests.get(url, params=params, timeout=30)
            logger.info(f"Сообщение отправлено в Telegram. Ответ: {response.json()}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в Telegram (попытка {attempt + 1}): {e}")
            if attempt < retry:
                time.sleep(5)
    return False

# Безопасная прокрутка страницы с таймаутом
def safe_scroll(driver, max_scroll_time=SCROLL_TIMEOUT):
    logger.info("Начинаем прокрутку страницы.")
    scroll_start_time = time.time()
    scroll_pause_time = 1
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Проверка на превышение времени прокрутки
        if time.time() - scroll_start_time > max_scroll_time:
            logger.warning(f"Превышено максимальное время прокрутки ({max_scroll_time} сек), продолжаем работу")
            break
            
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logger.info("Страница прокручена до конца.")
                break
            last_height = new_height
        except Exception as e:
            logger.error(f"Ошибка при прокрутке страницы: {e}")
            break

# URL страницы
url = "https://www.houseofmodelcars.com/eng/collection/formula-1/6?limit=192&sort=price&direction=asc&m=9+19+47+48+10+1+2&s=13&y=2024+2023+2022+2021+2020+2019+2018+2017+2007+2006+2001+2000"

# Основной цикл выполнения с защитой от сбоев
def main():
    driver = None
    try:
        driver = init_driver()
        error_counter = 0
        
        while True:
            try:
                logger.info("Запуск очередной проверки товаров на сайте.")
                
                # Проверка доступности сайта перед запуском Selenium
                if not check_site_availability(url):
                    logger.warning("Сайт недоступен, пропускаем текущую проверку")
                    time.sleep(60)  # Короткое ожидание перед следующей попыткой
                    continue
                
                previous_items = read_file()
                
                try:
                    logger.info(f"Загрузка страницы: {url}")
                    driver.get(url)
                except TimeoutException:
                    logger.error(f"Таймаут при загрузке страницы. Превышено {PAGE_LOAD_TIMEOUT} секунд.")
                    # Перезапускаем драйвер при таймауте
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                    driver = init_driver()
                    continue
                
                # Проверяем загрузку элементов
                if not wait_for_products(driver):
                    logger.warning("Не удалось дождаться загрузки товаров, пропускаем итерацию")
                    error_counter += 1
                    if error_counter >= 3:
                        # Перезапуск драйвера после нескольких ошибок
                        logger.warning("Слишком много ошибок подряд, перезапуск WebDriver")
                        if driver:
                            try:
                                driver.quit()
                            except:
                                pass
                        driver = init_driver()
                        error_counter = 0
                    continue
                
                # Сбрасываем счетчик ошибок при успешной загрузке
                error_counter = 0
                
                # Скроллим страницу с безопасным таймаутом
                safe_scroll(driver)
                
                # Получаем товары
                logger.info("Получение товаров с сайта.")
                products = driver.find_elements(By.CLASS_NAME, "col-12.col-sm-6.col-md-6.col-lg-4.col-xl-3")
                if not products:
                    logger.warning("Товары не найдены на странице!")
                    continue

                current_items = set()

                for product in products:
                    try:
                        info_tag = product.find_element(By.CLASS_NAME, "product-block-info-wrapper")
                        info = " ".join(info_tag.text.strip().split()).replace("Details »", "").strip()
                        current_items.add(info)
                    except Exception as e:
                        logger.error(f"Ошибка при обработке товара: {e}")
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
                else:
                    logger.info("Нет новых сообщений для отправки в Telegram.")

                # Обновляем файл, только если успешно получили товары
                if current_items:
                    logger.info("Обновление файла с данными.")
                    try:
                        with open(data_file, "w", encoding="utf-8") as f:
                            for item in sorted(current_items):
                                f.write(item + "\n")
                    except Exception as e:
                        logger.error(f"Ошибка при записи в файл: {e}")

                # Пауза между проверками (10 минут)
                logger.info(f"Ожидание перед следующей проверкой ({BETWEEN_CHECKS_INTERVAL/60} минут).")
                time.sleep(BETWEEN_CHECKS_INTERVAL)
                
            except WebDriverException as e:
                logger.error(f"Ошибка WebDriver: {e}")
                # Перезапускаем драйвер при проблемах
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                driver = init_driver()
                time.sleep(30)  # Ждем перед следующей попыткой
                
            except Exception as e:
                logger.error(f"Непредвиденная ошибка: {e}")
                # Отправляем уведомление об ошибке
                send_telegram_message(f"⚠️ Ошибка в работе бота: {e}", bot_token, chat_id)
                time.sleep(60)  # Ждем перед следующей попыткой

    except KeyboardInterrupt:
        logger.info("Остановлено пользователем.")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        send_telegram_message(f"❌ Критическая ошибка: {e}", bot_token, chat_id)
    finally:
        logger.info("Закрытие WebDriver.")
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Ошибка при закрытии WebDriver: {e}")

if __name__ == "__main__":
    main()