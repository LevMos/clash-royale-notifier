import os
import logging
import requests
from dotenv import load_dotenv
import urllib.parse
from flask import Flask, jsonify

app = Flask(__name__)
load_dotenv()

CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PLAYER_TAG = os.getenv("PLAYER_TAG")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

last_battle_time = None


@app.route("/")
def home():
    return "Bot is running", 200


@app.route("/check")
def check():
    global last_battle_time

    try:
        latest_time = get_latest_battle_time()

        if latest_time:
            if last_battle_time and latest_time != last_battle_time:
                send_telegram("🎮 Player just played a new battle!")

            last_battle_time = latest_time

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": str(e)}), 500


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
    response = requests.post(url, data=data)

    if response.status_code != 200:
        logging.error(f"Telegram error: {response.status_code}")
        logging.error(response.text)


def get_latest_battle_time():
    headers = {"Authorization": f"Bearer {CR_TOKEN}"}

    encoded_tag = urllib.parse.quote(PLAYER_TAG)
    url = f"https://api.clashroyale.com/v1/players/{encoded_tag}/battlelog"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        battles = response.json()
        if battles:
            return battles[0]["battleTime"]
    else:
        logging.error(f"Clash API error: {response.status_code}")
        logging.error(response.text)

    return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)