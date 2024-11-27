import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Загружаем переменные из файла api.env
load_dotenv(dotenv_path="api.env")

# Токен для Telegram бота и ID чата
TG_BOT_TOKEN = os.getenv('TG_BOT')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')  # ID чата для отправки сообщений

# Список твиттер-аккаунтов
accounts = [
    "zoruuuuu", "vuxzyethcrypto", "nonexistence", "ardizor", "nobrainflip",
    "CryptoNobler", "belizardd", "DeFi_Hanzo", "Dionysus_crypto", "hinkok_",
    "redkendl", "plutos_eth", "0xMentor_", "lenioneall", "0xDative", "CryptoShelter_",
    "0x_Doomer", "0xDPool"
]


# Получение данных с Dexscreener
def get_dexscreener_data():
    url = os.getenv("DEXSCREENER_API_URL", "https://api.dexscreener.com/token-boosts/top/v1")
    params = {'chainId': 'solana'}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()  # Получаем ответ в формате JSON

        if isinstance(data, dict):  # Проверяем, что это словарь
            return data.get("tokens", [])
        else:
            print(f"Неожиданный формат данных: {data}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении данных с Dexscreener: {e}")
        return []


# Функция для скрапинга твитов через Selenium
def get_tweets_from_twitter_via_selenium(account: str):
    # Настройка опций для Selenium WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Для скрытого режима
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Путь к драйверу (должен быть у вас установлен ChromeDriver)
    service = Service(executable_path="/path/to/chromedriver")  # Укажите путь к вашему chromedriver

    # Запуск WebDriver
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Переходим на страницу аккаунта
        driver.get(f"https://twitter.com/{account}")

        # Ожидаем загрузки страницы
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article')))

        # Получаем последние 10 твитов
        tweets = []
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article div[lang]")

        for tweet in tweet_elements[:10]:
            tweet_text = tweet.text.lower()  # Приводим к нижнему регистру
            tweets.append(tweet_text)

        return tweets

    except Exception as e:
        print(f"Ошибка при скрапинге твитов с аккаунта {account}: {e}")
        return []
    finally:
        driver.quit()


# Проверка токенов через RugCheck
def check_tokens_with_rugcheck(tokens):
    url = os.getenv("RUGCHECK_API_URL", "https://api.rugcheck.xyz/v1")
    results = []
    for token in tokens:
        try:
            response = requests.get(f"{url}/{token}")
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'Good':
                results.append(token)
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при проверке токена {token} через RugCheck: {e}")
    return results


# Отправка сообщения в Telegram
def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("Сообщение успешно отправлено в Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка отправки сообщения в Telegram: {e}")


# Команда /start
async def start(update: Update, context: CallbackContext) -> None:
    try:
        await update.message.reply_text('Привет! Я бот для анализа токенов. Используй команды для начала.')
    except Exception as e:
        print(f"Ошибка отправки сообщения в Telegram: {e}")


# Команда для анализа данных из Dexscreener
async def analyze_dexscreener(update: Update, context: CallbackContext) -> None:
    try:
        dexscreener_tokens = get_dexscreener_data()
        if not dexscreener_tokens:
            await update.message.reply_text("Не удалось получить данные с Dexscreener.")
            return
        message = "Топовые токены с Dexscreener:\n\n"
        for token in dexscreener_tokens[:10]:
            name = token.get("name", "N/A")
            ticker = token.get("symbol", "N/A")
            message += f"Токен: {name} ({ticker})\n\n"
        await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)
    except Exception as e:
        print(f"Ошибка при анализе Dexscreener: {e}")
        await update.message.reply_text("Произошла ошибка при анализе Dexscreener.")


# Команда для анализа твитов
async def analyze_twitter(update: Update, context: CallbackContext) -> None:
    try:
        all_tweets = []
        for account in accounts:
            tweets = get_tweets_from_twitter_via_selenium(account)
            all_tweets.extend(tweets)

        message = "Твиттер: найденные токены и тикеры:\n\n"
        for tweet in all_tweets[:10]:  # Берем только первые 10 твитов
            if "ca" in tweet or "token" in tweet or "pump" in tweet:
                message += f"- {tweet}\n"

        await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)
    except Exception as e:
        print(f"Ошибка при анализе твитов: {e}")
        await update.message.reply_text("Произошла ошибка при анализе твитов.")


# Основной код для запуска бота
def main() -> None:
    application = Application.builder().token(TG_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze_dexscreener", analyze_dexscreener))
    application.add_handler(CommandHandler("analyze_twitter", analyze_twitter))

    application.run_polling()


if __name__ == "__main__":
    main()