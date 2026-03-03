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
from datetime import datetime, timedelta, timezone

load_dotenv()
CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
from flask import send_from_directory

app = Flask(__name__)
check_lock = threading.Lock()

def check_new_battles():
    try:
        subscriptions = supabase.table("user_players") \
            .select("user_id, player_tag") \
            .execute().data

        if not subscriptions:
            logging.info("No tracked players.")
            return

        # ---- Уникальные player_tag ----
        unique_tags = list(set(sub["player_tag"] for sub in subscriptions))

        for tag in unique_tags:

            battles = get_battle_log(tag)
            if not battles:
                continue

            for battle in battles:
                battle_time = battle["battleTime"]

                exists = supabase.table("battles") \
                    .select("id") \
                    .eq("player_tag", tag) \
                    .eq("battle_time", battle_time) \
                    .execute()

                if exists.data:
                    continue

                try:
                    result = battle["team"][0]["crowns"] > battle["opponent"][0]["crowns"]
                except:
                    continue

                # ---- Сохраняем бой ----
                supabase.table("battles").insert({
                    "player_tag": tag,
                    "battle_time": battle_time,
                    "result": result
                }).execute()

                # ---- СТРИК ----
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

                streak_line = f"🔥 Win streak: {streak}" if streak > 1 else ""

                # ---- Средний gain за 10 ----
                last_10 = supabase.table("battles") \
                    .select("battle_time") \
                    .eq("player_tag", tag) \
                    .order("battle_time", desc=True) \
                    .limit(10) \
                    .execute().data

                total_change = 0
                count = 0

                for g in last_10:
                    matched = next(
                        (b for b in battles if b["battleTime"] == g["battle_time"]),
                        None
                    )
                    if matched:
                        tc = matched["team"][0].get("trophyChange")
                        if tc is not None:
                            total_change += tc
                            count += 1

                avg_line = f"📊 Avg (10): {round(total_change/count,1)}" if count > 0 else ""

                # ---- Формируем сообщение ----
                try:
                    player = battle["team"][0]
                    opponent = battle["opponent"][0]

                    player_name = player.get("name", "Unknown")
                    opponent_name = opponent.get("name", "Unknown")

                    player_crowns = player.get("crowns", 0)
                    opponent_crowns = opponent.get("crowns", 0)

                    game_mode = battle.get("gameMode", {}).get("name")
                    if game_mode:
                        battle_mode_line = f"⚔ {game_mode}"
                    else:
                        battle_mode_line = f"⚔ {battle.get('type', 'Unknown')}"

                    trophy_change = player.get("trophyChange")
                    starting_trophies = player.get("startingTrophies")

                    trophy_line = ""
                    trophies_total_line = ""

                    if trophy_change is not None:
                        if trophy_change > 0:
                            trophy_line = f"📈 +{trophy_change} 🏆"
                        elif trophy_change < 0:
                            trophy_line = f"📉 {trophy_change} 🏆"
                        else:
                            trophy_line = "➖ 0 🏆"

                        if starting_trophies is not None:
                            current_trophies = starting_trophies + trophy_change
                            trophies_total_line = f"🏆 Total: {current_trophies}"

                    status_line = "🏆 <b>Victory</b>" if result else "❌ <b>Defeat</b>"

                    lines = [
                        status_line,
                        "",
                        f"👤 <b>{player_name}</b>",
                        f"🆚 {opponent_name}",
                        "",
                        f"📊 {player_crowns} - {opponent_crowns}",
                    ]

                    if trophy_line:
                        lines.append(trophy_line)
                    if trophies_total_line:
                        lines.append(trophies_total_line)
                    if streak_line:
                        lines.append(streak_line)
                    if avg_line:
                        lines.append(avg_line)

                    lines.append(battle_mode_line)

                    message = "\n".join(lines)

                except Exception as e:
                    logging.error(f"Battle message build error: {e}")
                    continue

                # ---- Отправляем ВСЕМ подписчикам ----
                subscribers = [
                    s["user_id"]
                    for s in subscriptions
                    if s["player_tag"] == tag
                ]

                for chat_id in subscribers:
                    send_telegram(message, chat_id)

        logging.info("Battle check completed.")

    except Exception as e:
        logging.error(f"Battle check error: {e}")
def send_daily_reports():
    try:
        today = datetime.now(timezone.utc).date()

        
        last_sent = supabase.table("daily_report_log") \
            .select("report_date") \
            .order("report_date", desc=True) \
            .limit(1) \
            .execute().data

        if last_sent and last_sent[0]["report_date"] == str(today):
            logging.info("Daily report already sent today.")
            return
   
        users = supabase.table("users") \
            .select("id, daily_player_tag") \
            .not_.is_("daily_player_tag", "null") \
            .execute().data

        if not users:
            logging.info("No users with daily_player_tag.")
            return

        start = datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        for user in users:
            chat_id = user["id"]
            tag = user["daily_player_tag"]

            # --- Получаем игры за вчера ---
            response = supabase.table("battles") \
                .select("result") \
                .eq("player_tag", tag) \
                .gte("battle_time", start.isoformat()) \
                .lt("battle_time", end.isoformat()) \
                .order("battle_time", asc=True) \
                .execute()

            games = response.data
            if not games:
                continue

            total = len(games)
            wins = sum(1 for g in games if g["result"])
            losses = total - wins
            winrate = round((wins / total) * 100, 1)

            max_streak = 0
            current = 0
            for g in games:
                if g["result"]:
                    current += 1
                    max_streak = max(max_streak, current)
                else:
                    current = 0
            if winrate >= 65:
                status = "🔥 Шторм вырывается в"
                gif = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExMzBiamJmcmc1ZWdqcjdsMzQ4YTl0YnIwY2V2a2FrNndkY3dtbGpucyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/aR6tiTgr9WObz0VB8s/giphy.gif"
            elif winrate < 45:
                status = "💀 Шторм щедро раздал кубков соперникам сегодня"
                gif = "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExMmdzOHQyMDM0b3kxNmJ4NTZqdDdzcHV5dmx2Z2Via2V6bnI1bmhvdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/iDCXC1dqH2yu8PCyd8/giphy.gif"
            else:
                status = "⚖️ Шторм в копил элик сегодня"
                gif = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTlpOWZuOTlpajlzaWpobGZzdTRzb2dlMHRycXF5cGl5ZmRmeGc5YyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/g6qR2iAFg5UAX58Vd5/giphy.gif"
            message = (
                f"📊 <b>Daily Report — {tag}</b>\n\n"
                f"🎮 Games: {total}\n"
                f"🏆 Wins: {wins}\n"
                f"❌ Losses: {losses}\n"
                f"📈 Winrate: {winrate}%\n"
                f"🔥 Max streak: {max_streak}\n\n"
                f"{status}"
            )

            if gif:
                send_gif(chat_id, gif)
            send_telegram(message, chat_id)

        supabase.table("daily_report_log").insert({"report_date": str(today)}).execute()
        logging.info("Daily reports sent successfully.")

    except Exception as e:
        logging.error(f"Daily report error: {e}")
@app.route("/check", methods=["GET"])
def run_check():
    if check_lock.locked():
        return "Already running", 200
    with check_lock:
        check_new_battles()
    return "OK", 200

@app.route("/daily", methods=["GET"])
def run_daily():
    send_daily_reports()
    return "Daily reports sent", 200
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

def send_gif(chat_id, gif_url):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendAnimation"

        data = {
            "chat_id": chat_id,
            "animation": gif_url
        }

        requests.post(url, data=data, timeout=20)

    except Exception as e:
        logging.error(f"GIF send error: {e}")
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

def handle_message(message):
    try:
        chat_id = message["chat"]["id"]
        username = message["chat"].get("username")
        text = message.get("text", "").strip()

        register_user(chat_id, username)

        parts = text.split()
        command = parts[0]

        if command == "/start":
            send_telegram("👋 Welcome! Use /add #TAG to track a player", chat_id)

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

        elif command == "/winrate10":
            if len(parts) < 2:
                send_telegram("❌ Usage: /winrate10 #TAG", chat_id)
                return

            tag = parts[1]
            calculate_winrate(chat_id, tag, last_n=10)
        elif command == "/graph10":
            if len(parts) < 2:
                send_telegram("❌ Usage: /graph10 #TAG", chat_id)
                return

            tag = parts[1]
            send_winrate_graph(chat_id, tag, last_n=10)

        elif command == "/graph":
            if len(parts) < 2:
                send_telegram("❌ Usage: /graph #TAG", chat_id)
                return

            tag = parts[1]
            send_winrate_graph(chat_id, tag)

        elif command == "/winrate":
            if len(parts) < 2:
                send_telegram("❌ Usage: /winrate #TAG", chat_id)
                return

            tag = parts[1]
            calculate_winrate(chat_id, tag)
        elif command == "/dailyset":
            if len(parts) < 2:
                send_telegram("❌ Usage: /dailyset #TAG", chat_id)
                return

            tag = parts[1].upper()
            exists = supabase.table("user_players") \
                .select("id") \
                .eq("user_id", chat_id) \
                .eq("player_tag", tag) \
                .execute()

            if not exists.data:
                send_telegram("❌ You are not tracking this player. Use /add first.", chat_id)
                return

            supabase.table("users") \
                .update({"daily_player_tag": tag}) \
                .eq("id", chat_id) \
                .execute()

            send_telegram(f"✅ Daily report set for {tag}", chat_id)

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

        elif command == "/help":
            send_telegram(
                "/add #TAG\n"
                "/list\n"
                "/winrate #TAG\n"
                "/winrate10 #TAG\n"
                "/remove #TAG",
                chat_id
            )
        elif command == "лох":
            gif_url = "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExb3RnbXlwYXo1dWc1Z3BrNWh5NzRhem00bzB2MWw3dGU3Z3pidTQ1YyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/qwGtSvKLr3Ae0aydDy/giphy.gif"
            send_gif(chat_id, gif_url)

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