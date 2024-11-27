import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from dotenv import load_dotenv
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
            all_tocken.append({"url" : i["url"],
                               "tokenAddress" : i["tokenAddress"]})
        return all_tocken
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении данных с Dexscreener: {e}")
        return []


# Получение твитов с аккаунтов через Selenium (реализуйте или используйте другой метод)
def get_tweets_from_twitter_via_selenium(account):
    # Здесь должен быть код для скрапинга твитов через Selenium (реализация по вашему запросу)
    # Для упрощения примера, вернем фейковые данные
    return [f"Tweet from {account} mentioning CA token", f"Another tweet from {account} mentioning tokenX"]


# Проверка токенов через RugCheck
def check_tokens_with_rugcheck(tokens):
    url = os.getenv("RUGCHECK_API_URL", "https://api.rugcheck.xyz/v1/tokens")
    results = []
    for token in tokens:
        try:
            response = requests.get(f"{url}/{token}/report/summary")
            response.raise_for_status()
            data = response.json()
            for i in data['risks']:
                if i['level'] == 'danger':
                    break
            else:
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
    await update.message.reply_text('Привет! Я бот для анализа токенов. Используй команды для начала.')


# Команда для анализа данных из Dexscreener
async def analyze_dexscreener(update: Update, context: CallbackContext) -> None:
    dexscreener_tokens = get_dexscreener_data()
    if not dexscreener_tokens:
        await update.message.reply_text("Не удалось получить данные с Dexscreener.")
        return
    message = "Топовые токены с Dexscreener:\n\n"
    for token in dexscreener_tokens:
        message += f"Token: {token['tokenAddress']}\nURL: {token['url']}\n\n"
    await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)


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
    message = "Результаты анализа токенов:\n\n"
    for token in good_tokens:
        message += f"Токен: {token}\n"
    await send_telegram_message(TG_BOT_TOKEN, TG_CHAT_ID, message)


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
