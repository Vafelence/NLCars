from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
import requests

# Настройки Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")  # Запуск без интерфейса
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

# Автоматическая установка ChromeDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# URL страницы
url = "https://www.houseofmodelcars.com/eng/collection/formula-1/6?limit=192&sort=price&direction=asc&m=9+19+47+48+10+1+2&s=13&y=2024+2023+2022+2021+2020+2019+2018+2017+2007+2006+2001+2000"

# Функция для чтения данных из файла
def read_file():
    try:
        with open("model_info.txt", "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    except FileNotFoundError:
        return set()

# Функция для отправки сообщений в Telegram
def send_telegram_message(message, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message,
    }
    response = requests.get(url, params=params)
    return response.json()

# Токен вашего Telegram-бота и ID чата
bot_token = "6858480572:AAGUJwUq_UevIhrbQS6cG2nN0hfyDw8yh54"
chat_id = "-4134676016"  # Например, ID группового чата или личного чата с ботом

while True:
    # Читаем данные из файла при каждой итерации
    previous_items = read_file()

    driver.get(url)

    # Скроллим вниз, чтобы подгрузить все элементы
    scroll_pause_time = 2
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # Получаем все блоки товаров
    products = driver.find_elements(By.CLASS_NAME, "col-12.col-sm-6.col-md-6.col-lg-4.col-xl-3")

    # Список найденных позиций
    current_items = set()

    for product in products:
        info_tag = product.find_element(By.CLASS_NAME, "product-block-info-wrapper")

        info = " ".join(info_tag.text.strip().split("\n")) if info_tag else "Нет информации"

        # Убираем "Details »" из информации, если оно есть
        info = info.replace("Details »", "").strip()

        # Добавляем только информацию
        current_items.add(info)

    # Сравниваем текущие и предыдущие позиции
    new_models = current_items - previous_items
    ended_models = previous_items - current_items

    # Флаг для записи в файл
    changes_detected = False

    message = ""

    if new_models or ended_models:
        changes_detected = True

        if new_models:
            message += "\n🔥 Новые модели в Голландии:\n"
            for item in sorted(new_models):
                message += "+ " + item + "\n"

        if ended_models:
            message += "\n❌ Закончились модели в Голландии:\n"
            for item in sorted(ended_models):
                message += "- " + item + "\n"
    else:
        message = "Изменений нет в Голландии."

    # Отправляем сообщение в Telegram, если есть изменения или нет изменений
    send_telegram_message(message, bot_token, chat_id)

    # Записываем новые данные в файл
    with open("model_info.txt", "w", encoding="utf-8") as f:
        for item in sorted(current_items):
            f.write(item + "\n")

    # Ждём 1 минуту перед следующей проверкой
    time.sleep(600)

# Закрываем браузер
driver.quit()
