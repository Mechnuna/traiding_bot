import os
import requests
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv
import time
import asyncio

# Загружаем переменные из файла .env
load_dotenv(dotenv_path="api.env")

# Конфигурация
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
RUGCHECK_API_URL = os.getenv("RUGCHECK_API_URL", "https://api.rugcheck.xyz/v1/tokens")
DEXSCREENER_API_URL = os.getenv("DEXSCREENER_API_URL", "https://api.dexscreener.com/token-boosts/top/v1")

# Асинхронный Telegram Bot
bot = Bot(token=TG_BOT_TOKEN)

def format_market_cap(mc):
    """Форматирует значение MarketCap в миллионы, если оно превышает 1000k."""
    if mc >= 1000000:
        return f"{mc // 1000000}M"  # Преобразуем в миллионы
    elif mc >= 1000:
        return f"{mc // 1000}k"  # Преобразуем в тысячи
    return str(mc)  # Если меньше, просто возвращаем как есть

async def fetch_dexscreener_tokens(limit=20):
    """
    Получает список токенов с Dexscreener API. Берет не более `limit` токенов.
    """
    try:
        response = requests.get(DEXSCREENER_API_URL)
        response.raise_for_status()
        data = response.json()  # API возвращает список токенов

        tokens = []
        for token in data[:limit]:  # Берем только первые `limit` токенов
            token_address = token.get('tokenAddress')
            if token_address:
                token_data = {
                    'tokenAddress': token_address,
                    'url': token.get('url', "N/A"),
                    'links': token.get('links', []),
                    'totalAmount': token.get('totalAmount', 0),
                    'priceChange5m': token.get('priceChange5m', "N/A"),
                    'priceChange1h': token.get('priceChange1h', "N/A"),
                }
                tokens.append(token_data)

        return tokens
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении токенов с Dexscreener: {e}")
        return []

async def check_tokens_with_rugcheck(tokens, max_retries=3, delay=15):
    """
    Проверяет токены через RugCheck с обработкой ошибок и задержкой в случае превышения лимита.
    """
    results = []
    for token in tokens:
        token_address = token.get("tokenAddress")

        if not token_address:
            print(f"Пропуск токена из-за отсутствия tokenAddress: {token}")
            continue

        retries = 0
        while retries < max_retries:
            try:
                # Получаем информацию о токене с RugCheck
                response = requests.get(f"{RUGCHECK_API_URL}/{token_address}/report/summary")
                response.raise_for_status()
                data = response.json()

                # Получаем тикер из данных
                ticker = data.get("symbol")

                # Проверяем уровень риска
                risks = data.get("risks", [])
                if any(risk.get("level") == "danger" for risk in risks):
                    print(f"Токен {token_address}: Danger 🔴")
                    results.append({"tokenAddress": token_address, "status": "Danger 🔴", "ticker": ticker})
                else:
                    print(f"Токен {token_address}: Good 🟢")
                    results.append({"tokenAddress": token_address, "status": "Good 🟢", "ticker": ticker})

                break  # Успешный запрос, выходим из цикла повторов
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:  # Если превышен лимит запросов
                    print(f"Превышен лимит запросов для токена {token_address}, повторная попытка через {delay} секунд...")
                    retries += 1
                    time.sleep(delay)  # Задержка перед повтором
                else:
                    print(f"Ошибка при проверке токена {token_address} через RugCheck: {e}")
                    break
            except requests.exceptions.RequestException as e:
                print(f"Ошибка при проверке токена {token_address} через RugCheck: {e}")
                break

    return results

async def send_telegram_report(update: Update, context):
    """
    Формирует и отправляет отчет в Telegram.
    """
    # Получаем токены с Dexscreener (максимум 20)
    tokens = await fetch_dexscreener_tokens(limit=20)

    # Прогоняем токены через RugCheck
    analysis_results = await check_tokens_with_rugcheck(tokens)

    message = "Анализ токенов за последние 24ч:\n\n"

    for idx, token in enumerate(tokens, start=1):  # Берем токены из ограниченного списка
        token_address = token.get("tokenAddress")
        url = token.get("url", "N/A")
        mc = format_market_cap(token.get("totalAmount", 0))  # здесь нужно правильно получить MC
        rug_status = next(
            (result["status"] for result in analysis_results if result["tokenAddress"] == token_address),
            "Неизвестно"
        )
        ticker = next(
            (result["ticker"] for result in analysis_results if result["tokenAddress"] == token_address),
            "Неизвестно"
        )

        # Формируем данные для токена
        name = f"${ticker}"  # Теперь отображаем тикер
        price_change_5m = token.get("priceChange5m", "N/A")
        price_change_1h = token.get("priceChange1h", "N/A")

        message += (
            f"{idx}. {ticker} - token: {token_address}\n"
            f"URL: {url}\n"
            f"MC: {mc}\n"
            f"5M: {price_change_5m}%\n"
            f"1H: {price_change_1h}%\n"
            f"Rugcheck: {rug_status}\n\n"
        )

    try:
        await update.message.reply_text(message)
        print("Отчет успешно отправлен в Telegram.")
    except Exception as e:
        print(f"Ошибка при отправке отчета в Telegram: {e}")

async def start(update: Update, context):
    """
    Начальная команда для отправки отчета
    """
    await update.message.reply_text("Отправка отчета... Пожалуйста, подождите.")
    await send_telegram_report(update, context)

def main():
    """
    Настройка бота и обработка команд
    """
    # Создаем асинхронное приложение бота
    application = Application.builder().token(TG_BOT_TOKEN).build()

    # Добавляем команду "/start" для отправки отчета
    application.add_handler(CommandHandler("start", start))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()
