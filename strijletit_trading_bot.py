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
import json

# Загружаем переменные из файла .env
load_dotenv(dotenv_path=".env")

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
        with open('all_token.json','w') as f:
            json.dump(response.json(), f)
        all_tocken = []
        for i in response.json():
            result = {
            link.get("label", link.get("type")): link["url"] 
            for link in i["links"] 
            if "url" in link
            }
            result["url"] = i["url"]
            result["tokenAddress"] = i["tokenAddress"]
            all_tocken.append(result)
        return all_tocken
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
    chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )


    # Путь к драйверу (должен быть у вас установлен ChromeDriver)
    service = Service(executable_path="./chromedriver-mac-arm64/chromedriver")  # Укажите путь к вашему chromedriver

    # Запуск WebDriver
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Переходим на страницу аккаунта
        driver.get(f"https://x.com/{account}")
        print("start")

        # Ожидаем загрузки страницы
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article')))
        print("get css selector")
        # Получаем последние 10 твитов
        tweets = []
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article div[lang]")
        print("find css selector")
        for tweet in tweet_elements[:10]:
            tweet_text = tweet.text.lower()  # Приводим к нижнему регистру
            tweets.append(tweet_text)
        print("add tweet")

        return tweets

    except TimeoutException:
        print(f"Тайм-аут при загрузке твитов с аккаунта {account}.")
        return []
    except WebDriverException as e:
        print(f"Ошибка WebDriver при скрапинге аккаунта {account}: {e}")
        return []
    except Exception as e:
        print(f"Ошибка при скрапинге твитов с аккаунта {account}: {e}")
        return []
    finally:
        driver.quit()

# Проверка токенов через RugCheck
def check_tokens_with_rugcheck(tokens):
    url = os.getenv("RUGCHECK_API_URL", "https://api.rugcheck.xyz/v1/tokens")
    results = []
    for token in tokens:
        try:
            response = requests.get(f"{url}/{token}/report")
            response.raise_for_status()
            data = response.json()
            for i in data['risks']:
                if i['level'] == 'danger':
                    break
            else:
                results.append({'token': data['mint'], 
                                'symbol': data['tokenMeta']['symbol'],
                                'risk': data['score']})

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
    await update.message.reply_text('Привет! Я бот для анализа токенов. Используй команды для начала.')


# Команда для анализа данных из Dexscreener
async def analyze_dexscreener(update: Update, context: CallbackContext) -> None:
    dexscreener_tokens = get_dexscreener_data()
    if not dexscreener_tokens:
        await update.message.reply_text("Не удалось получить данные с Dexscreener.")
        return
    # message = "Топовые токены с Dexscreener:\n\n"
    # for token in dexscreener_tokens:
    #     for k,v in token.items():
    #         message += f"{k} {v}\n"
    #     message += "\n\n"
    # print(message)
    # await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)
    # Формируем сообщения
    messages = []
    current_message = "Топовые токены с Dexscreener:\n\n"
    for token in dexscreener_tokens:
        token_info = "\n".join([f"{k}: {v}" for k, v in token.items()])
        token_info += "\n\n"
        
        # Если длина текущего сообщения превысит 4000 символов, создаём новое сообщение
        if len(current_message) + len(token_info) > 4000:
            messages.append(current_message)
            current_message = ""
        
        current_message += token_info
    
    # Добавляем последнее сообщение
    if current_message:
        messages.append(current_message)

    # Отправляем сообщения в Telegram
    for msg in messages:
        await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, msg)


# Команда для анализа твитов
async def analyze_twitter(update: Update, context: CallbackContext) -> None:
    all_tweets = []
    for account in accounts:
        tweets = get_tweets_from_twitter_via_selenium(account)
        all_tweets.extend(tweets)

    message = "Твиттер: найденные токены и тикеры:\n\n"
    for tweet in all_tweets[:10]:  # Берем только первые 10 твитов
        if "CA" in tweet or "token" in tweet:
            message += f"- {tweet}\n"

    await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)


# Команда для поиска токенов в Twitter
async def search_twitter_token(update: Update, context: CallbackContext) -> None:
    token = " ".join(context.args)  # Получаем аргументы команды
    if token:
        message = f"Ищем токен {token} в Twitter...\n"
        await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)
    else:
        await update.message.reply_text("Пожалуйста, укажите токен для поиска.")


# Общий анализ всех данных
async def analyze(update: Update, context: CallbackContext) -> None:
    # Получаем токены из Dexscreener и твиттер
    dexscreener_tokens = get_dexscreener_data()[:10]

    #TODO
    # all_tweets = []
    # for account in accounts:
    #     tweets = get_tweets_from_twitter_via_selenium(account)
    #     all_tweets.extend(tweets)

    # Прогоняем токены через RugCheck
    tokens = [token["tokenAddress"] for token in dexscreener_tokens]
    good_tokens = check_tokens_with_rugcheck(tokens)

    # Сортируем результаты и отправляем в Telegram
    # message = "Результаты анализа токенов:\n\n"
    # for token in good_tokens:
    #     message += f"Токен: {token}\n"
        
    # await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)
    # Формируем сообщения
    messages = []
    current_message = "Результаты анализа токенов:\n\n"
    
    for token in good_tokens:
        token_info = "\n".join([f"{k}: {v}" for k, v in token.items()])
        token_info += "\n\n"
        
        # Если длина текущего сообщения превысит 4000 символов, создаём новое сообщение
        if len(current_message) + len(token_info) > 4000:
            messages.append(current_message)
            current_message = ""
        
        current_message += token_info
    # Добавляем последнее сообщение
    if current_message:
        messages.append(current_message)

    # Отправляем сообщения в Telegram
    for msg in messages:
        print(msg)  # Для отладки
        await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, msg)


# Основной код для запуска бота
def main() -> None:
    application = Application.builder().token(TG_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze_dexscreener", analyze_dexscreener))
    application.add_handler(CommandHandler("analyze_twitter", analyze_twitter))
    application.add_handler(CommandHandler("search_twitter_token", search_twitter_token))
    application.add_handler(CommandHandler("analyze", analyze))

    application.run_polling()


if __name__ == "__main__":
    main()
