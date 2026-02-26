import os
import logging
import requests
import urllib.parse
import threading
from flask import Flask, request
from dotenv import load_dotenv
from supabase import create_client, Client

# =============================
# INIT
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

# Блокировка чтобы /check не запускался параллельно
check_lock = threading.Lock()

# =============================
# TELEGRAM
# =============================

def send_telegram(message, chat_id):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        response = requests.post(url, data=data, timeout=10)

        if response.status_code != 200:
            logging.error(f"Telegram error: {response.status_code}")
            logging.error(response.text)

    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# =============================
# CLASH API
# =============================

def get_battle_log(player_tag):
    try:
        headers = {"Authorization": f"Bearer {CR_TOKEN}"}
        encoded_tag = urllib.parse.quote(player_tag)
        url = f"https://api.clashroyale.com/v1/players/{encoded_tag}/battlelog"

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()

        logging.error(f"{player_tag} | Clash API error: {response.status_code}")
        logging.error(response.text)

    except Exception as e:
        logging.error(f"Clash API request failed: {e}")

    return []

# =============================
# USER MANAGEMENT
# =============================

def register_user(chat_id, username=None):
    try:
        existing = supabase.table("users").select("id").eq("id", chat_id).execute()

        if not existing.data:
            supabase.table("users").insert({
                "id": chat_id,
                "username": username
            }).execute()
    except Exception as e:
        logging.error(f"Register user error: {e}")

# =============================
# WINRATE
# =============================

def calculate_winrate(chat_id, tag, limit=None):
    try:
        subscription = supabase.table("user_players") \
            .select("id") \
            .eq("user_id", chat_id) \
            .eq("player_tag", tag) \
            .execute()

        if not subscription.data:
            send_telegram("❌ You are not tracking this player.", chat_id)
            return

        query = supabase.table("battles") \
            .select("result") \
            .eq("player_tag", tag) \
            .order("battle_time", desc=True)

        if limit:
            query = query.limit(limit)

        response = query.execute()

        games = response.data
        total = len(games)

        if total == 0:
            send_telegram("No games yet", chat_id)
            return

        wins = sum(1 for g in games if g.get("result") is True)
        rate = round((wins / total) * 100, 1)

        title = f"Last {limit} games" if limit else "All games"

        message = (
            f"📊 <b>Winrate for {tag}</b>\n"
            f"<i>{title}</i>\n\n"
            f"Games: {total}\n"
            f"Wins: {wins}\n"
            f"Winrate: {rate}%"
        )

        send_telegram(message, chat_id)

    except Exception as e:
        logging.error(f"Winrate error: {e}")
        send_telegram("⚠ Error calculating winrate.", chat_id)
# =============================
# TELEGRAM COMMAND HANDLER
# =============================

def handle_message(message):
    try:
        chat_id = message["chat"]["id"]
        username = message["chat"].get("username")
        text = message.get("text", "").strip()

        logging.info(f"Message from {chat_id}: {text}")

        register_user(chat_id, username)

        if text.startswith("/start"):
            send_telegram("👋 Welcome! Use /add #TAG to track a player", chat_id)

        elif text.startswith("/add"):
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
            tag = text.split(" ")[1].upper()
            calculate_winrate(chat_id, tag)

        elif text.startswith("/remove"):
            tag = text.split(" ")[1].upper()

            supabase.table("user_players") \
                .delete() \
                .eq("user_id", chat_id) \
                .eq("player_tag", tag) \
                .execute()

            send_telegram(f"🗑 Removed {tag}", chat_id)

        elif text.startswith("/help"):
            send_telegram(
                "/add #TAG\n"
                "/list\n"
                "/winrate #TAG\n"
                "/winrate10 #TAG\n"
                "/remove #TAG",
                chat_id
                        )
        elif text.startswith("/winrate10"):
            parts = text.split(" ")
            if len(parts) < 2:
                send_telegram("❌ Usage: /winrate10 #TAG", chat_id)
                return

            tag = parts[1].upper()
            calculate_winrate(chat_id, tag, limit=10)

        else:
            send_telegram("❌ Unknown command", chat_id)

    except Exception as e:
        logging.error(f"Handle message error: {e}")

# =============================
# CHECK MATCHES
# =============================

def run_check():

    response = supabase.table("user_players").select("player_tag").execute()
    tags = list(set(p["player_tag"] for p in response.data))

    for tag in tags:

        existing_battles = supabase.table("battles") \
            .select("id") \
            .eq("player_tag", tag) \
            .limit(1) \
            .execute()

        first_sync = len(existing_battles.data) == 0

        battles = get_battle_log(tag)
        if not battles:
            continue

        battle = battles[0]
        battle_time = battle["battleTime"]

        exists = supabase.table("battles") \
            .select("id") \
            .eq("player_tag", tag) \
            .eq("battle_time", battle_time) \
            .execute()

        if exists.data:
            continue

        player = next(
            (p for p in battle["team"] if p["tag"].upper() == tag),
            None
        )

        if not player:
            continue

        opponent = battle["opponent"][0]

        player_name = player["name"]
        opponent_name = opponent["name"]
        player_crowns = player["crowns"]
        opponent_crowns = opponent["crowns"]
        trophy_change = player.get("trophyChange", 0)
        mode = battle.get("gameMode", {}).get("name", "Unknown")

        result = player_crowns > opponent_crowns

        supabase.table("battles").insert({
            "player_tag": tag,
            "battle_time": battle_time,
            "result": result,
            "player_crowns": player_crowns,
            "opponent_crowns": opponent_crowns,
            "trophy_change": trophy_change,
            "game_mode": mode
        }).execute()

        if not first_sync:
            users = supabase.table("user_players") \
                .select("user_id") \
                .eq("player_tag", tag) \
                .execute()

            result_text = "🏆 Victory" if result else "❌ Defeat"

            message = (
                f"<b>{result_text}</b>\n\n"
                f"👤 <b>{player_name}</b>\n"
                f"🆚 {opponent_name}\n\n"
                f"📊 {player_crowns} - {opponent_crowns}\n"
                f"📈 {trophy_change}\n"
                f"⚔ <i>{mode}</i>"
            )

            for user in users.data:
                send_telegram(message, user["user_id"])

# =============================
# ROUTES
# =============================

@app.route("/check")
def check():
    try:
        if not check_lock.acquire(blocking=False):
            return {"status": "already running"}, 200

        run_check()
        return {"status": "ok"}, 200

    except Exception as e:
        logging.error(f"CHECK ERROR: {e}")
        return {"status": "error"}, 200

    finally:
        if check_lock.locked():
            check_lock.release()

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if "message" in data:
            handle_message(data["message"])
        return "ok", 200

    except Exception as e:
        logging.error(f"WEBHOOK ERROR: {e}")
        return "ok", 200

@app.route("/")
def home():
    return "Bot is running", 200

# =============================
# RUN
# =============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)