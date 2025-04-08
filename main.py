from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
import logging

# Настройки для PhantomJS
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Файл с сохранённой информацией
data_file = "model_info.txt"

# Telegram
bot_token = "6858480572:AAGUJwUq_UevIhrbQS6cG2nN0hfyDw8yh54"
chat_id = "-4134676016"

# Настройки PhantomJS
phantomjs_path = "/usr/local/bin/phantomjs"  # Замените на путь к вашему PhantomJS, если нужно
driver = webdriver.PhantomJS(executable_path=phantomjs_path)

driver.set_window_size(1280, 1024)  # Устанавливаем размер окна, если нужно
driver.implicitly_wait(20)  # Увеличенное глобальное ожидание (поиск элементов)

# URL страницы
url = "https://www.houseofmodelcars.com/eng/collection/formula-1/6?limit=192&sort=price&direction=asc&m=9+19+47+48+10+1+2&s=13&y=2024+2023+2022+2021+2020+2019+2018+2017+2007+2006+2001+2000"

# Функция ожидания появления хотя бы одного элемента
def wait_for_products(timeout=30):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, "product-block-info-wrapper"))
    )

# Чтение данных из файла
def read_file():
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    except FileNotFoundError:
        return set()

# Отправка сообщений в Telegram
def send_telegram_message(message, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message,
    }
    response = requests.get(url, params=params)
    return response.json()

# Основной цикл
try:
    logger.info("Бот запущен.")
    while True:
        previous_items = read_file()
        driver.get(url)

        wait_for_products()  # Ждём, пока хотя бы один товар загрузится

        # Скроллим до конца
        scroll_pause_time = 2
        last_height = driver.execute_script("return document.body.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Получаем товары
        products = driver.find_elements(By.CLASS_NAME, "col-12.col-sm-6.col-md-6.col-lg-4.col-xl-3")
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
        send_telegram_message(message, bot_token, chat_id)

        # Обновляем файл
        with open(data_file, "w", encoding="utf-8") as f:
            for item in sorted(current_items):
                f.write(item + "\n")

        # Пауза между проверками (10 минут)
        time.sleep(600)

except KeyboardInterrupt:
    logger.info("Остановлено пользователем.")
finally:
    driver.quit()
