import requests
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import snscrape.modules.twitter as sntwitter

# --- Константы ---
DEXSCREENER_API_LATEST = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_API_TOKENS = "https://api.dexscreener.com/latest/dex/tokens/"
DEXSCREENER_API_BOOSTS = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_API_LATEST_BOOSTS = "https://api.dexscreener.com/token-boosts/latest/v1"
RUGCHECK_API = "https://api.rugcheck.xyz/v1"
NETWORK = "Solana"
AGE_THRESHOLD_HOURS = 24
TXNS_1H_THRESHOLD = 50
TXNS_5M_THRESHOLD = 5
TELEGRAM_BOT_TOKEN = "7039309217:AAHC7sD40OyjrEBpyGTleLzpTLEqy-VoRP4"


# --- Функции анализа ---

# 1. Функция для получения списка токенов с DexScreener
def fetch_tokens_from_dexscreener():
    print("Запрос к DexScreener API...")
    response = requests.get(DEXSCREENER_API_LATEST)
    if response.status_code == 200:
        data = response.json()
        print("Ответ от DexScreener:", data)  # Логируем ответ

        tokens = []
        if isinstance(data, list):  # Проверяем, что это список
            for pair in data:
                # Добавим проверку, чтобы избежать ошибок с отсутствующими ключами
                chain = pair.get('chain', None)  # Безопасно получаем 'chain'
                volume = pair.get('volume', {})
                pair_created_at = pair.get('pairCreatedAt', None)

                if (
                        chain == NETWORK and  # Проверяем, что chain существует
                        volume.get('h1', {}).get('count', 0) >= TXNS_1H_THRESHOLD and
                        volume.get('m5', {}).get('count', 0) >= TXNS_5M_THRESHOLD and
                        pair_created_at and
                        (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(
                            pair_created_at)).total_seconds() / 3600 <= AGE_THRESHOLD_HOURS
                ):
                    tokens.append({
                        "contract": pair.get('address', 'Не указан'),
                        "symbol": pair.get('baseToken', {}).get('symbol', 'Не указан'),
                        "social_links": pair.get('socials', {}),
                    })
        else:
            print("Ответ от API не является списком, структура ответа отличается.")

        return tokens
    else:
        print(f"Ошибка при запросе к DexScreener: {response.status_code}")
        return []

# 2. Получить данные по одному или нескольким токенам
def fetch_token_data_by_address(address):
    url = f"{DEXSCREENER_API_TOKENS}{address}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при запросе токенов по адресу {address}: {response.status_code}")
        return {}


# 3. Проверка контракта через Rugcheck
def check_contract_with_rugcheck(contract_address):
    print(f"Проверка контракта {contract_address} через Rugcheck...")
    response = requests.get(f"{RUGCHECK_API}/{contract_address}")
    if response.status_code == 200:
        data = response.json()
        print("Ответ от Rugcheck:", data)  # Логируем ответ
        return data.get('status', '') == 'good' and not data.get('topHolders', {}).get('isMajorityOwned', True)
    else:
        print(f"Ошибка при запросе к Rugcheck для {contract_address}: {response.status_code}")
    return False


# 4. Анализ аудитории через TweetScout
def evaluate_social_audience(social_links):
    twitter_url = social_links.get('twitter')
    if not twitter_url:
        return {"influencers": 0, "degenerates": 0, "top_followers": 0}

    handle = twitter_url.split("/")[-1]
    print(f"Анализ аудитории для аккаунта Twitter: {handle}")
    response = requests.get(f"{TWEETSCOUT_API}account/{handle}/quality")
    if response.status_code == 200:
        data = response.json()
        print("Ответ от TweetScout:", data)  # Логируем ответ
        influencers = data['influencers']
        degenerates = data['degenerates']
        top_followers = len([f for f in data['followers'] if f['followerCount'] >= 45000])
        return {"influencers": influencers, "degenerates": degenerates, "top_followers": top_followers}
    else:
        print(f"Ошибка при запросе к TweetScout для {handle}: {response.status_code}")
    return {"influencers": 0, "degenerates": 0, "top_followers": 0}


# 5. Анализ Twitter хайпа
def analyze_twitter_hype(symbol):
    print(f"Анализ хайпа для {symbol} в Twitter...")
    tweets = []
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(f"{symbol}").get_items()):
        if i >= 5:
            break
        tweets.append(f"🔹 @{tweet.user.username}: {tweet.content}")
    return "\n".join(tweets)


# --- Telegram обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Запуск бота...")
    # 1. Получаем токены с DexScreener
    tokens = fetch_tokens_from_dexscreener()
    results = []

    for token in tokens:
        contract = token["contract"]
        symbol = token["symbol"]
        social_links = token["social_links"]

        # 2. Проверяем контракт через Rugcheck
        is_good_contract = check_contract_with_rugcheck(contract)

        # 3. Анализируем аудиторию в TweetScout
        social_quality = evaluate_social_audience(social_links)

        # 4. Анализ хайпа в Twitter
        twitter_hype = analyze_twitter_hype(symbol)

        # Формируем результат
        if is_good_contract:
            results.append(
                f"🔹 {symbol} ({contract}):\n"
                f"📊 Аудитория: Инфлюенсеры: {social_quality['influencers']}, "
                f"Дегенераты: {social_quality['degenerates']}, "
                f"Топ фолловеры: {social_quality['top_followers']}\n"
                f"🐦 Хайп в Twitter:\n{twitter_hype}\n"
                f"📜 Ссылки: {social_links}\n"
            )

    # Отправляем результаты
    if results:
        await update.message.reply_text("\n\n".join(results))
    else:
        await update.message.reply_text("Нет подходящих токенов по заданным фильтрам.")


if __name__ == "__main__":
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()