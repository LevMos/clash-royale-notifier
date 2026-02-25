import os
import logging
import requests
from dotenv import load_dotenv
import urllib.parse
from flask import Flask, jsonify, request
import re


app = Flask(__name__)
load_dotenv()

CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
PLAYER_TAGS = os.getenv("PLAYER_TAGS").split(",")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

last_battle_times = {}

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        handle_message(data["message"])

    return "ok", 200

users = {}

@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/check")
def check():

    try:
        for tag in PLAYER_TAGS:

            battles = get_battle_log(tag)

            if not battles:
                continue

            # первый запуск — просто запоминаем последний бой
            if tag not in last_battle_times:
                last_battle_times[tag] = battles[0]["battleTime"]
                continue

            # перебираем от старых к новым
            for battle in reversed(battles):

                battle_time = battle["battleTime"]

                if battle_time <= last_battle_times[tag]:
                    continue

                player = battle["team"][0]
                opponent = battle["opponent"][0]

                player_name = player["name"]
                opponent_name = opponent["name"]

                player_crowns = player["crowns"]
                opponent_crowns = opponent["crowns"]

                result = "🏆 Victory" if player_crowns > opponent_crowns else "❌ Defeat"

                trophy_change = player.get("trophyChange", 0)

                if trophy_change > 0:
                    trophy_text = f"📈 +{trophy_change}"
                elif trophy_change < 0:
                    trophy_text = f"📉 {trophy_change}"
                else:
                    trophy_text = "➖ 0"

                mode = battle.get("gameMode", {}).get("name", "Unknown")

                logging.info(
                    f"{player_name} | {result} | "
                    f"{player_crowns}-{opponent_crowns} | "
                    f"Trophies: {trophy_change}"
                )

                message = (
                    f"<b>{result}</b>\n\n"
                    f"👤 <b>{player_name}</b>\n"
                    f"🆚 {opponent_name}\n\n"
                    f"📊 <b>Score:</b> {player_crowns} - {opponent_crowns}\n"
                    f"{trophy_text}\n"
                    f"⚔ <i>{mode}</i>"
                )

                for user_chat_id, user_data in users.items():
                    if tag in user_data["players"]:
                        user_data["stats"][tag].append(player_crowns > opponent_crowns)
                        send_telegram(message, user_chat_id)

            # обновляем последний обработанный бой
            last_battle_times[tag] = battles[0]["battleTime"]

        return {"status": "ok"}, 200

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return {"error": str(e)}, 500

def calculate_winrate(chat_id, tag):

    if tag not in users[chat_id]["stats"]:
        send_telegram("❌ Player not found", chat_id)
        return

    games = users[chat_id]["stats"][tag]

    if not games:
        send_telegram("No games yet", chat_id)
        return

    wins = sum(games)
    total = len(games)
    rate = round((wins / total) * 100, 1)

    message = (
        f"📊 <b>Winrate for {tag}</b>\n\n"
        f"Games: {total}\n"
        f"Wins: {wins}\n"
        f"Winrate: {rate}%"
    )

    send_telegram(message, chat_id)

def handle_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # Логируем все входящие сообщения
    logging.info(f"Received message from {chat_id}: {text}")

    # Если пользователь новый — регистрируем его
    if chat_id not in users:
        users[chat_id] = {"players": [], "stats": {}}
        logging.info(f"New user registered: {chat_id}")

    # Обработка команд
    if text.startswith("/start"):
        logging.info(f"User {chat_id} executed /start")
        send_telegram("👋 Welcome! Use /add #TAG to track a player", chat_id)

    elif text.startswith("/add"):
        try:
            tag = text.split(" ")[1].upper()
            if tag in users[chat_id]["players"]:
                send_telegram(f"⚠ {tag} is already added.", chat_id)
                logging.info(f"User {chat_id} tried to add duplicate tag {tag}")
                return

            users[chat_id]["players"].append(tag)
            users[chat_id]["stats"][tag] = []
            send_telegram(f"✅ Added {tag}", chat_id)
            logging.info(f"User {chat_id} added player {tag}")

        except IndexError:
            send_telegram("❌ Usage: /add #TAG", chat_id)
            logging.warning(f"User {chat_id} used /add incorrectly")

    elif text.startswith("/list"):
        players = users[chat_id]["players"]
        send_telegram("📋 Your players:\n" + ("\n".join(players) if players else "No players added"), chat_id)
        logging.info(f"User {chat_id} executed /list")

    elif text.startswith("/winrate"):
        try:
            tag = text.split(" ")[1].upper()
            logging.info(f"User {chat_id} requested winrate for {tag}")
            calculate_winrate(chat_id, tag)
        except IndexError:
            send_telegram("❌ Usage: /winrate #TAG", chat_id)
            logging.warning(f"User {chat_id} used /winrate incorrectly")

    elif text.startswith("/remove"):
        try:
            tag = text.split(" ")[1].upper()
            if tag in users[chat_id]["players"]:
                users[chat_id]["players"].remove(tag)
                users[chat_id]["stats"].pop(tag, None)
                send_telegram(f"🗑 Removed {tag}", chat_id)
                logging.info(f"User {chat_id} removed player {tag}")
            else:
                send_telegram(f"⚠ {tag} not found in your list", chat_id)
                logging.info(f"User {chat_id} tried to remove nonexistent tag {tag}")
        except IndexError:
            send_telegram("❌ Usage: /remove #TAG", chat_id)
            logging.warning(f"User {chat_id} used /remove incorrectly")

    elif text.startswith("/help"):
        help_message = (
            "📖 <b>Bot Commands:</b>\n\n"
            "/start - 👋 Start and register yourself\n"
            "/add #TAG - ➕ Add a player to track\n"
            "/list - 📋 Show your players\n"
            "/winrate #TAG - 📊 Show player's winrate\n"
            "/remove #TAG - 🗑 Remove a player\n"
            "/help - ❓ Show this help message"
        )
        send_telegram(help_message, chat_id)
        logging.info(f"User {chat_id} requested /help")

    else:
        send_telegram("❌ Unknown command. Use /help", chat_id)
        logging.warning(f"User {chat_id} sent unknown command: {text}")

        
def send_telegram(message, chat_id):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    response = requests.post(url, data=data)

    if response.status_code != 200:
        logging.error(f"Telegram error: {response.status_code}")
        logging.error(response.text)

def get_battle_log(player_tag):
    headers = {"Authorization": f"Bearer {CR_TOKEN}"}
    encoded_tag = urllib.parse.quote(player_tag)
    url = f"https://api.clashroyale.com/v1/players/{encoded_tag}/battlelog"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"{player_tag} | Clash API error: {response.status_code}")
        logging.error(response.text)

    return []


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)