import os
import logging
import requests
import urllib.parse
import threading
import io
import matplotlib.pyplot as plt
from flask import Flask, request
from dotenv import load_dotenv
from supabase import create_client, Client
# ============================
# INIT
# =============================
load_dotenv()
CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
from flask import send_from_directory

app = Flask(__name__)
check_lock = threading.Lock()
# =============================
# BATTLE CHECK (CRON)
# =============================
def check_new_battles():
    try:
        users = supabase.table("user_players").select("user_id, player_tag").execute().data

        if not users:
            logging.info("No tracked players.")
            return

        for sub in users:
            chat_id = sub["user_id"]
            tag = sub["player_tag"]

            battles = get_battle_log(tag)
            if not battles:
                continue

            latest = battles[0]
            battle_time = latest["battleTime"]
            exists = supabase.table("battles") \
                .select("id") \
                .eq("player_tag", tag) \
                .eq("battle_time", battle_time) \
                .execute()
            if exists.data:
                continue
            try:
                result = latest["team"][0]["crowns"] > latest["opponent"][0]["crowns"]
            except:
                continue
            supabase.table("battles").insert({
                "player_tag": tag,
                "battle_time": battle_time,
                "result": result
            }).execute()
            recent_games = supabase.table("battles") \
                .select("result") \
                .eq("player_tag", tag) \
                .order("battle_time", desc=True) \
                .limit(20) \
                .execute().data
            streak = 0
            for g in recent_games:
                if g["result"]:
                    streak += 1
                else:
                    break
            if streak > 1:
                streak_line = f"🔥 Win streak: {streak}"
            else:
                streak_line = ""
            last_10 = supabase.table("battles") \
                .select("result, battle_time") \
                .eq("player_tag", tag) \
                .order("battle_time", desc=True) \
                .limit(10) \
                .execute().data
            total_change = 0
            count = 0
            for g in last_10:
                battle = next((b for b in battles if b["battleTime"] == g["battle_time"]), None)
                if battle:
                    tc = battle["team"][0].get("trophyChange")
                    if tc is not None:
                        total_change += tc
                        count += 1
            if count > 0:
                avg_change = round(total_change / count, 1)
                avg_line = f"📊 Avg (10): {avg_change}"
            else:
                avg_line = ""
            try:
                player = latest["team"][0]
                opponent = latest["opponent"][0]

                player_name = player.get("name", "Unknown")
                opponent_name = opponent.get("name", "Unknown")

                player_crowns = player.get("crowns", 0)
                opponent_crowns = opponent.get("crowns", 0)
                trophy_change = player.get("trophyChange", 0)    
                game_mode = latest.get("gameMode", {}).get("name", None)
                if game_mode:
                    battle_mode_line = f"⚔ {game_mode}"
                else:
                    raw_type = latest.get("type", "Unknown")
                    battle_mode_line = f"⚔ {raw_type}"
                starting_trophies = player.get("startingTrophies")
                trophy_change = player.get("trophyChange")

                if trophy_change is not None:
                    if trophy_change > 0:
                        trophy_line = f"📈 +{trophy_change} 🏆"
                    elif trophy_change < 0:
                        trophy_line = f"📉 {trophy_change} 🏆"
                    else:
                        trophy_line = "➖ 0 🏆"
                else:
                    trophy_line = " "

                if starting_trophies is not None and trophy_change is not None:
                    current_trophies = starting_trophies + trophy_change
                    trophies_total_line = f"🏆 Total: {current_trophies}"
                else:
                    trophies_total_line = ""

                if result:
                    status_line = "🏆 <b>Victory</b>"
                else:
                    status_line = "❌ <b>Defeat</b>"
                message = (
                    f"{status_line}\n\n"
                    f"👤 <b>{player_name}</b>\n"
                    f"🆚 {opponent_name}\n\n"
                    f"📊 {player_crowns} - {opponent_crowns}\n"
                    f"{trophy_line}\n"
                    f"{streak_line}\n"
                    f"{avg_line}\n"
                    f"⚔ {battle_mode_line}"
                )
                send_telegram(message, chat_id)

            except Exception as e:
                logging.error(f"Battle message build error: {e}")

                logging.info("Battle check completed.")

    except Exception as e:
                    logging.error(f"Battle message build error: {e}")

@app.route("/check", methods=["GET"])
def run_check():
    if check_lock.locked():
        return "Already running", 200

    with check_lock:
        check_new_battles()

    return "OK", 200

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
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

        requests.post(url, data=data, timeout=10)

    except Exception as e:
        logging.error(f"Telegram send error: {e}")

def send_photo(chat_id, image_bytes):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        files = {
            "photo": ("graph.png", image_bytes)
        }
        data = {
            "chat_id": chat_id
        }
        requests.post(url, data=data, files=files, timeout=20)

    except Exception as e:
        logging.error(f"Telegram photo send error: {e}")
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

    except Exception as e:
        logging.error(f"Clash API request failed: {e}")

    return []
# ============================
# GRAPH BUILD
# ============================
def send_winrate_graph(chat_id, tag, last_n=None):
    try:
        tag = tag.upper()

        response = supabase.table("battles") \
            .select("result, battle_time") \
            .eq("player_tag", tag) \
            .order("battle_time", desc=False) \
            .execute()

        games = response.data

        if not games:
            send_telegram("No games to build graph.", chat_id)
            return

        if last_n:
            games = games[-last_n:]

        cumulative_rates = []
        wins = 0

        for i, g in enumerate(games, start=1):
            if g["result"] == True:
                wins += 1
            cumulative_rates.append((wins / i) * 100)

        # --- Строим график ---
        plt.figure()
        plt.plot(range(1, len(cumulative_rates) + 1), cumulative_rates)
        plt.xlabel("Games")
        plt.ylabel("Winrate %")
        plt.title(f"Winrate progression for {tag}")
        plt.ylim(0, 100)

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        plt.close()
        buffer.seek(0)

        send_photo(chat_id, buffer)

    except Exception as e:
        logging.error(f"Graph error: {e}")
        send_telegram("⚠ Error building graph.", chat_id)
# =============================
# WINRATE
# =============================
def calculate_winrate(chat_id, tag, last_n=None):
    try:
        tag = tag.upper()

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

        if last_n:
            query = query.range(0, last_n - 1)

        response = query.execute()
        games = response.data

        total = len(games)

        if total == 0:
            send_telegram("No games yet.", chat_id)
            return

        wins = sum(1 for g in games if g["result"] is True)
        rate = round((wins / total) * 100, 1)

        title = f"Last {total} games" if last_n else "All games"

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
# TELEGRAM HANDLER
# =============================
def handle_message(message):
    try:
        chat_id = message["chat"]["id"]
        username = message["chat"].get("username")
        text = message.get("text", "").strip()

        register_user(chat_id, username)

        parts = text.split()
        command = parts[0]

        # -------- START --------
        if command == "/start":
            send_telegram("👋 Welcome! Use /add #TAG to track a player", chat_id)

        # -------- ADD --------
        elif command == "/add":
            if len(parts) < 2:
                send_telegram("❌ Usage: /add #TAG", chat_id)
                return

            tag = parts[1].upper()

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

        # -------- LIST --------
        elif command == "/list":
            response = supabase.table("user_players") \
                .select("player_tag") \
                .eq("user_id", chat_id) \
                .execute()

            players = [p["player_tag"] for p in response.data]

            send_telegram(
                "📋 Your players:\n" + ("\n".join(players) if players else "No players added"),
                chat_id
            )

        # -------- WINRATE 10 --------
        elif command == "/winrate10":
            if len(parts) < 2:
                send_telegram("❌ Usage: /winrate10 #TAG", chat_id)
                return

            tag = parts[1]
            calculate_winrate(chat_id, tag, last_n=10)
                    # -------- GRAPH 10 --------
        elif command == "/graph10":
            if len(parts) < 2:
                send_telegram("❌ Usage: /graph10 #TAG", chat_id)
                return

            tag = parts[1]
            send_winrate_graph(chat_id, tag, last_n=10)

        # -------- GRAPH ALL --------
        elif command == "/graph":
            if len(parts) < 2:
                send_telegram("❌ Usage: /graph #TAG", chat_id)
                return

            tag = parts[1]
            send_winrate_graph(chat_id, tag)

        # -------- WINRATE ALL --------
        elif command == "/winrate":
            if len(parts) < 2:
                send_telegram("❌ Usage: /winrate #TAG", chat_id)
                return

            tag = parts[1]
            calculate_winrate(chat_id, tag)

        # -------- REMOVE --------
        elif command == "/remove":
            if len(parts) < 2:
                send_telegram("❌ Usage: /remove #TAG", chat_id)
                return

            tag = parts[1].upper()

            supabase.table("user_players") \
                .delete() \
                .eq("user_id", chat_id) \
                .eq("player_tag", tag) \
                .execute()

            send_telegram(f"🗑 Removed {tag}", chat_id)

        # -------- HELP --------
        elif command == "/help":
            send_telegram(
                "/add #TAG\n"
                "/list\n"
                "/winrate #TAG\n"
                "/winrate10 #TAG\n"
                "/remove #TAG",
                chat_id
            )

        else:
            send_telegram("❌ Unknown command", chat_id)

    except Exception as e:
        logging.error(f"Handle message error: {e}")
# =============================
# WEBAPP BUTTON
# =============================
def send_webapp_button(chat_id, tag):
    url = f"https://your-app.onrender.com/app?tag={tag}"

    keyboard = {
        "inline_keyboard": [[
            {
                "text": "📊 Open Interactive Dashboard",
                "web_app": {"url": url}
            }
        ]]
    }

    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"Interactive stats for {tag}",
            "reply_markup": keyboard
        }
    )
# =============================
# USER REGISTER
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
# ROUTES
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)