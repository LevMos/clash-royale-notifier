import os
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PLAYER_TAG = os.getenv("PLAYER_TAG")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 120))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

last_battle_time = None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print("Status:", response.status_code)
        print("Body:", response.text)
        logging.error(f"Telegram error: {response.status_code}")


def get_latest_battle_time():
    headers = {"Authorization": f"Bearer {CR_TOKEN}"}
    url = f"https://api.clashroyale.com/v1/players/{PLAYER_TAG}/battlelog"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        battles = response.json()
        if battles:
            return battles[0]["battleTime"]
    else:
        logging.error(f"Clash API error: {response.status_code}")

    return None
  
def print_render_ip():
    try:
        response = requests.get("https://api.ipify.org")
        if response.status_code == 200:
            logging.info(f"Render Public IP: {response.text}")
        else:
            logging.error(f"IP check failed: {response.status_code}")
    except Exception as e:
        logging.error(f"IP detection error: {e}")

def main():
    global last_battle_time

    logging.info("Bot started")

    while True:
        try:
            latest_time = get_latest_battle_time()

            if latest_time:
                if last_battle_time and latest_time != last_battle_time:
                    send_telegram("🎮 Player just played a new battle!")

                last_battle_time = latest_time

        except Exception as e:
            logging.error(f"Unexpected error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
