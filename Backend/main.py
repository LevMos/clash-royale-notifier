import os
import logging
import requests
import urllib.parse
import threading
import io
import random
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
NIGHT_WIN_MESSAGES = [
    "🌙 Ночная победа",
    "🌙 Ночные катки приносят победу",
    "🦉 Кто-то играет слишком поздно",
    "🌌 Арена не спит"
]
NIGHT_LOSE_MESSAGES = [
    "😴 Похоже пора спать",
    "🌙 Ночные катки не задались",
    "🛌 Может лучше завтра",
    "🌌 Арена ночью беспощадна"
]
FIRST_GAME_WIN = [
    "🌅 Отличное начало дня",
    "☀ День начинается с победы",
    "🔥 Первая кровь на арене сегодня"
]
FIRST_GAME_LOSE = [
    "☕ День начинается тяжело",
    "😴 Нужно ещё проснуться",
    "📉 Не самое лучшее начало дня"
]
THREE_ZERO_MESSAGES = [
    "💥 Легчайшая для величайшого",
    "👑 Без шансов",
    "⚡ ez 3-0",
    "🏆 Идеальная игра",
    "🔥 Соперника испепилила спарки ШТОРМА",
    "🤑 Мое имя Дорого, фамилия Богато"
]
ZERO_THREE_MESSAGES = [
    "💀 это минус вайбик (и кубки)",
    "🪦 Проебуньки от штормуньки",
    "🤕 Может поменяем колоду?",
    "📉 Больно смотреть",
    "🚑 Шторм бы гордился.....и беймил"
]
WIN_STREAK_MESSAGES = {
    3: [
        "⚡ Победная серия начинается",
        "🔥 Скоро разбор от 5-ти кратного чемпиона",
        "🎯 3 победы - он идет по стопам штормика ",
    ],
    5: [
        "🔥 Легчайшая 5я победа",
        "🚀 Как же он силен",
        "💪 Сегодня арена его",
    ],
    7: [
        "🚀 Серия становится пугающей",
        "👀 Перепсываем колоду",
        "⚔ Это ради митер Л?",
    ],
    10: [
        "👑 ПОЛНОЕ УНИЧТОЖЕНИЕ",
        "🏆 ШТОООООООРМ",
        "💀 Соперники могут расходиться",
    ]
}
LOSE_STREAK_MESSAGES = {
    3: [
        "🫠 Сегодня карты явно против него",
        "🤕 Допустимый урон",
        "📉 Отвлекли немного",
    ],
    5: [
        "💀 По беймрейту выиграл зато",
        "🪦 Кто-то забыл как побеждать",
        "🥶 Неприятный человек попался",
    ],
    8: [
        "🚑 После такого удаляют клеш...",
        "🧯 Че закибербулили тебя да?",
        "😭 МИМИМИМИМИМИМИМИМИМИ",
    ]
}
good_results = [
    (
        "🔥 Шторм разрывает арену сегодня",
        "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExMzBiamJmcmc1ZWdqcjdsMzQ4YTl0YnIwY2V2a2FrNndkY3dtbGpucyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/aR6tiTgr9WObz0VB8s/giphy.gif"
    ),
    (
        "⚡ Сегодня соперники просто не успевали ставить карты",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3M3dtdDVqNG5pZmF0Mndqb202Z2EzcHNiZGpxc3FnaDJvajN1YTVpYyZlcD12MV9zdGlja2Vyc19zZWFyY2gmY3Q9cw/U3I2Eko8KQfWKxMMqP/giphy.gif"
    ),
    (
        "🏆 Арена сегодня принадлежала Шторму",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOW5xczVxaXpsbWZmbGZleGgzZ2ljYmYxMGQ0dHM1emRuMmt2YWMweCZlcD12MV9zdGlja2Vyc19zZWFyY2gmY3Q9cw/ky9bxpYbxyuFZJEmwX/giphy.gif"
    )
]
bad_results = [
    (
        "💀 Шторм щедро раздал кубков соперникам сегодня",
        "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExMmdzOHQyMDM0b3kxNmJ4NTZqdDdzcHV5dmx2Z2Via2V6bnI1bmhvdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/iDCXC1dqH2yu8PCyd8/giphy.gif"
    ),
    (
        "🪦 Сегодня арена была безжалостна",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3NTl3anY2c2FhbDZ1djV0aXB5MGE2YTFvNHZraHloanIyOHhhM3h2YiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/wka72YWgDbNlCa7OeP/giphy.gif"
    ),
    (
        "🥀 День был тяжёлый…",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmh2czVjc2VjMTN4M3J5aGFxcjRudGxhbTA3ZHhvMmVodXBvM3p2diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/EBeKznBAtxaH9uChgk/giphy.gif"
    )
]
mid_results = [
    (
        "⚖️ Шторм копил эликсир сегодня",
        "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTlpOWZuOTlpajlzaWpobGZzdTRzb2dlMHRycXF5cGl5ZmRmeGc5YyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/g6qR2iAFg5UAX58Vd5/giphy.gif"
    ),
    (
        "😐 День прошёл без особых потрясений",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbXZ1NjBhenl6dmJ4MDJ6OTRoajh6Zmo2aXAzZXdpd2c0YWd2aWFxaCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/480kfa3gt1vO04dYzW/giphy.gif"
    ),
    (
        "🎮 Рабочий день на арене",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExc3huM21mMmZ0NmJ1OWNkbm13NGxtZHdjeWZwdmkwYmR4M28ycndrcyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dGiuYXO8T9YljuwcNn/giphy.gif"
    )
]

def get_player_name(tag):
    tag = tag.replace("#", "")
    url = f"https://proxy.royaleapi.dev/v1/players/%23{tag}"
    headers = {"Authorization": f"Bearer {CR_TOKEN}"} 
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None

    data = r.json()

    return data.get("name")

def get_random_streak_message(streak, pool):
    eligible = [k for k in pool.keys() if streak >= k]

    if not eligible:
        return ""

    level = max(eligible)
    return random.choice(pool[level])
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
                raw_time = battle["battleTime"]
                parsed_time = datetime.strptime(
                    raw_time, "%Y%m%dT%H%M%S.%fZ"
                ).replace(tzinfo=timezone.utc)
                battle_time = parsed_time.isoformat()
                battle_hour = parsed_time.hour
                today = parsed_time.date()
                today_battles = supabase.table("battles") \
                    .select("id") \
                    .eq("player_tag", tag) \
                    .gte("battle_time", today.isoformat()) \
                    .limit(1) \
                    .execute().data
                is_first_game = len(today_battles) == 0
                is_night = battle_hour >= 0 and battle_hour < 6
                night_line = ""
                if is_night:
                    if result:
                        night_line = random.choice(NIGHT_WIN_MESSAGES)
                    else:
                        night_line = random.choice(NIGHT_LOSE_MESSAGES)

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
                win_streak = 0
                lose_streak = 0
                for g in recent_games:
                    if g["result"]:
                        if lose_streak == 0:
                            win_streak += 1
                        else:
                            break
                    else:
                        if win_streak == 0:
                            lose_streak += 1
                        else:
                            break

                streak_line = ""
                meme_line = ""

                if win_streak > 1:
                    streak_line = f"🔥 Win streak: {win_streak}"
                    meme_line = get_random_streak_message(win_streak, WIN_STREAK_MESSAGES)

                elif lose_streak > 1:
                    streak_line = f"💀 Lose streak: {lose_streak}"
                    meme_line = get_random_streak_message(lose_streak, LOSE_STREAK_MESSAGES)
                if random.random() < 0.03:
                    meme_line = random.choice([
                        "🤖 Бот подозревает использование чит-кодов",
                        "👀 Supercell уже наблюдает",
                        "🧠 IQ этой колоды явно выше среднего"
                    ])
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
                    player_name = player.get("name", "Unknown")
                    opponent_name = opponent.get("name", "Unknown")
                    player_trophies = battle["team"][0].get("startingTrophies", 0)
                    opponent_trophies = battle["opponent"][0].get("startingTrophies", 0)

                    # --- Проверяем ник в базе ---
                    user_record = supabase.table("users") \
                        .select("player_name") \
                        .eq("daily_player_tag", tag) \
                        .execute().data

                    if user_record:
                        stored_name = user_record[0]["player_name"]

                        if stored_name != player_name:
                            supabase.table("users") \
                                .update({"player_name": player_name}) \
                                .eq("daily_player_tag", tag) \
                                .execute()
                    player_crowns = player.get("crowns", 0)
                    opponent_crowns = opponent.get("crowns", 0)
                    special_line = ""

                    if player_crowns == 3 and opponent_crowns == 0:
                        special_line = random.choice(THREE_ZERO_MESSAGES)

                    elif player_crowns == 0 and opponent_crowns == 3:
                        special_line = random.choice(ZERO_THREE_MESSAGES)

                    game_mode = battle.get("gameMode", {}).get("name")
                    if game_mode:
                        battle_mode_line = f"⚔ {game_mode}"
                    else:
                        battle_mode_line = f"⚔ {battle.get('type', 'Unknown')}"

                    trophy_change = player.get("trophyChange")
                    starting_trophies = player.get("startingTrophies")

                    first_game_line = ""

                    if is_first_game:
                        if result:
                            first_game_line = random.choice(FIRST_GAME_WIN)
                        else:
                            first_game_line = random.choice(FIRST_GAME_LOSE)

                    if night_line:
                        lines.append(night_line)

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
                        f"👤 <b>{player_name}</b> ({player_trophies}🏆)",
                        f"🆚 {opponent_name} ({opponent_trophies}🏆)",
                        "",
                        f"📊 {player_crowns} - {opponent_crowns}",
                    ]

                    if trophy_line:
                        lines.append(trophy_line)
                    if trophies_total_line:
                        lines.append(trophies_total_line)
                    if streak_line:
                        lines.append(streak_line)
                    if meme_line:
                        lines.append(meme_line)
                    if avg_line:
                        lines.append(avg_line)
                    if special_line:
                        lines.append(special_line)
                    if first_game_line:
                        lines.append(first_game_line)

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
        users = supabase.table("users") \
            .select("id, daily_player_tag, player_name") \
            .not_.is_("daily_player_tag", "null") \
            .execute().data
        logging.info("Daily endpoint triggered")


        if not users:
            logging.info("No users with daily_player_tag.")
            return

        start = datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        for user in users:
            chat_id = user["id"]
            tag = user["daily_player_tag"]
            name = user.get("player_name") or tag

            # --- Получаем игры за вчера ---
            response = supabase.table("battles") \
                .select("result") \
                .eq("player_tag", tag) \
                .gte("battle_time", start.isoformat()) \
                .lt("battle_time", end.isoformat()) \
                .order("battle_time") \
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
                status, gif = random.choice(good_results)

            elif winrate < 45:
                status, gif = random.choice(bad_results)

            else:
                status, gif = random.choice(mid_results)

            if gif:
                send_gif(chat_id, gif)
            message = (
                f"📊 <b>Daily Report — {name}</b>\n\n"
                f"🎮 Games: {total}\n"
                f"🏆 Wins: {wins}\n"
                f"❌ Losses: {losses}\n"
                f"📈 Winrate: {winrate}%\n"
                f"🔥 Max streak: {max_streak}\n\n"
                f"{status}"
            )

            send_telegram(message, chat_id)
            supabase.table("daily_report_log").upsert(
                {
                    "user_id": chat_id,
                    "report_date": str(today)
                },
                on_conflict="user_id,report_date"
            ).execute()
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
        tag = player_tag.replace("#", "")
        url = f"https://proxy.royaleapi.dev/v1/players/%23{tag}/battlelog"
        headers = {"Authorization": f"Bearer {CR_TOKEN}"}  # ← добавить
        response = requests.get(url, headers=headers, timeout=10)

        logging.info(f"RESPONSE → {response.status_code}")

        if response.status_code == 200:
            return response.json()

        logging.error(f"{player_tag} | Proxy error: {response.status_code} | {response.text}")

    except Exception as e:
        logging.error(f"Proxy request failed: {e}")

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
            player_name = get_player_name(tag)

            supabase.table("users") \
                .update({
                    "daily_player_tag": tag,
                    "player_name": player_name
                }) \
                .eq("id", chat_id) \
                .execute()
            display = player_name if player_name else tag
            send_telegram(f"✅ Daily report set for {display}", chat_id)

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