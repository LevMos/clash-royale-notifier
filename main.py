import os
import logging
import requests
from dotenv import load_dotenv
import urllib.parse
from flask import Flask, jsonify
import re


app = Flask(__name__)
load_dotenv()

CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PLAYER_TAGS = os.getenv("PLAYER_TAGS").split(",")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

last_battle_times = {}



@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/check")
def check():

    try:
        for tag in PLAYER_TAGS:

            battle = get_latest_battle(tag)

            if not battle:
                continue

            battle_time = battle["battleTime"]

            # первый запуск для игрока
            if tag not in last_battle_times:
                last_battle_times[tag] = battle_time
                continue

            if battle_time != last_battle_times[tag]:

                player = battle["team"][0]
                opponent = battle["opponent"][0]

                player_name = player["name"]
                opponent_name = opponent["name"]


                player_crowns = player["crowns"]
                opponent_crowns = opponent["crowns"]

                result = "🏆 Victory" if player_crowns > opponent_crowns else "❌ Defeat"

                # изменение трофеев
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
                    f"{result}\n\n"
                    f"👤 <b>{player_name}</b>\n"
                    f"🆚 {opponent_name}\n\n"
                    f"📊 Score: <b>{player_crowns} - {opponent_crowns}</b>\n"
                    f"{trophy_text}\n"
                    f"⚔ Mode: {mode}"
                        )
                
                send_telegram(message)

                last_battle_times[tag] = battle_time

        return {"status": "ok"}, 200

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return {"error": str(e)}, 500
    

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    response = requests.post(url, data=data)

    if response.status_code != 200:
        logging.error(f"Telegram error: {response.status_code}")
        logging.error(response.text)

def get_latest_battle(player_tag):
    headers = {"Authorization": f"Bearer {CR_TOKEN}"}

    encoded_tag = urllib.parse.quote(player_tag)
    url = f"https://api.clashroyale.com/v1/players/{encoded_tag}/battlelog"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        battles = response.json()
        if battles:
            return battles[0]
    else:
        logging.error(f"{player_tag} | Clash API error: {response.status_code}")
        logging.error(response.text)

    return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)