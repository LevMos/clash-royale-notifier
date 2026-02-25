import os
import logging
import requests
import urllib.parse
from flask import Flask, request
from dotenv import load_dotenv
from supabase import create_client, Client

# =============================
#INIT
# =============================

load_dotenv()

CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# =============================
#TELEGRAM
# =============================

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

# =============================
# CLASH API
# =============================

def get_battle_log(player_tag):
    headers = {"Authorization": f"Bearer {CR_TOKEN}"}
    encoded_tag = urllib.parse.quote(player_tag)
    url = f"https://api.clashroyale.com/v1/players/{encoded_tag}/battlelog"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()

    logging.error(f"{player_tag} | Clash API error: {response.status_code}")
    logging.error(response.text)
    return []

# =============================
#USER MANAGEMENT
# =============================

def register_user(chat_id, username=None):
    existing = supabase.table("users").select("id").eq("id", chat_id).execute()

    if not existing.data:
        supabase.table("users").insert({
            "id": chat_id,
            "username": username
        }).execute()

# =============================
#WINRATE
# =============================

def calculate_winrate(chat_id, tag):

    # Проверяем, подписан ли пользователь на игрока
    subscription = supabase.table("user_players") \
    .select("id") \
    .eq("user_id", chat_id) \
    .eq("player_tag", tag) \
    .execute()

    if not subscription.data:
        send_telegram("❌ You are not tracking this player.", chat_id)
        return
    
    response = supabase.table("battles") \
        .select("result") \
        .eq("player_tag", tag) \
        .execute()

    games = response.data

    if not games:
        send_telegram("No games yet", chat_id)
        return

    wins = sum(1 for g in games if g["result"] is True)
    if total == 0:
        send_telegram("No games yet", chat_id)
        return
    total = len(games)
    rate = round((wins / total) * 100, 1)

    message = (
        f"📊 <b>Winrate for {tag}</b>\n\n"
        f"Games: {total}\n"
        f"Wins: {wins}\n"
        f"Winrate: {rate}%"
    )

    send_telegram(message, chat_id)

# =============================
#TELEGRAM COMMAND HANDLER
# =============================

def handle_message(message):
    chat_id = message["chat"]["id"]
    username = message["chat"].get("username")
    text = message.get("text", "").strip()

    logging.info(f"Message from {chat_id}: {text}")

    register_user(chat_id, username)

    if text.startswith("/start"):
        send_telegram("👋 Welcome! Use /add #TAG to track a player", chat_id)

    elif text.startswith("/add"):
        try:
            tag = text.split(" ")[1].upper()

            existing = supabase.table("user_players") \
                .select("*") \
                .eq("user_id", chat_id) \
                .eq("player_tag", tag) \
                .execute()

            if existing.data:
                send_telegram(f"⚠ {tag} already added.", chat_id)
                return

            supabase.table("user_players").insert({
                "user_id": chat_id,
                "player_tag": tag
            }).execute()

            send_telegram(f"✅ Added {tag}", chat_id)

        except IndexError:
            send_telegram("❌ Usage: /add #TAG", chat_id)

    elif text.startswith("/list"):
        response = supabase.table("user_players") \
            .select("player_tag") \
            .eq("user_id", chat_id) \
            .execute()

        players = [p["player_tag"] for p in response.data]

        send_telegram(
            "📋 Your players:\n" + ("\n".join(players) if players else "No players added"),
            chat_id
        )

    elif text.startswith("/winrate"):
        try:
            tag = text.split(" ")[1].upper()
            calculate_winrate(chat_id, tag)
        except IndexError:
            send_telegram("❌ Usage: /winrate #TAG", chat_id)

    elif text.startswith("/remove"):
        try:
            tag = text.split(" ")[1].upper()

            supabase.table("user_players") \
                .delete() \
                .eq("user_id", chat_id) \
                .eq("player_tag", tag) \
                .execute()

            send_telegram(f"🗑 Removed {tag}", chat_id)

        except IndexError:
            send_telegram("❌ Usage: /remove #TAG", chat_id)

    elif text.startswith("/help"):
        help_message = (
            "📖 <b>Bot Commands:</b>\n\n"
            "/start - 👋 Register\n"
            "/add #TAG - ➕ Track player\n"
            "/list - 📋 Show players\n"
            "/winrate #TAG - 📊 Winrate\n"
            "/remove #TAG - 🗑 Remove player\n"
            "/help - ❓ Help"
        )
        send_telegram(help_message, chat_id)

    else:
        send_telegram("❌ Unknown command. Use /help", chat_id)

# =============================
#CHECK NEW MATCHES
# =============================

@app.route("/check")
def check():

    response = supabase.table("user_players").select("player_tag").execute()
    tags = list(set(p["player_tag"] for p in response.data))

    for tag in tags:
        # Проверяем есть ли уже матчи в базе
        existing_battles = supabase.table("battles") \
            .select("id") \
            .eq("player_tag", tag) \
            .limit(1) \
            .execute()

        first_sync = len(existing_battles.data) == 0

        battles = get_battle_log(tag)

        for battle in reversed(battles):

            battle_time = battle["battleTime"]

            # Проверяем, есть ли уже такой бой
            exists = supabase.table("battles") \
                .select("id") \
                .eq("player_tag", tag) \
                .eq("battle_time", battle_time) \
                .execute()

            if exists.data:
                continue

            player = battle["team"][0]
            opponent = battle["opponent"][0]

            player_crowns = player["crowns"]
            opponent_crowns = opponent["crowns"]
            trophy_change = player.get("trophyChange", 0)
            mode = battle.get("gameMode", {}).get("name", "Unknown")

            result = player_crowns > opponent_crowns

            # Сохраняем бой
            supabase.table("battles").insert({
                "player_tag": tag,
                "battle_time": battle_time,
                "result": result,
                "player_crowns": player_crowns,
                "opponent_crowns": opponent_crowns,
                "trophy_change": trophy_change,
                "game_mode": mode
            }).execute()

            # Отправляем уведомление подписанным пользователям
            users = supabase.table("user_players") \
                .select("user_id") \
                .eq("player_tag", tag) \
                .execute()

            result_text = "🏆 Victory" if result else "❌ Defeat"

            message = (
                f"<b>{result_text}</b>\n\n"
                f"📊 Score: {player_crowns} - {opponent_crowns}\n"
                f"📈 Trophies: {trophy_change}\n"
                f"⚔ {mode}"
            )

            # Отправляем уведомления только если это НЕ первая синхронизация
            if not first_sync:
                for user in users.data:
                    send_telegram(message, user["user_id"])

    return {"status": "ok"}, 200

# =============================
#WEBHOOK
# =============================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        handle_message(data["message"])

    return "ok", 200

@app.route("/")
def home():
    return "Bot is running", 200

# =============================
#RUN
# =============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)