import logging
import requests

from config import TG_TOKEN

API_URL = f"https://api.telegram.org/bot{TG_TOKEN}"


def _post(method, timeout, **kwargs):
    try:
        response = requests.post(f"{API_URL}/{method}", timeout=timeout, **kwargs)
        if not response.ok:
            logging.error("Telegram %s failed: %s %s", method, response.status_code, response.text)
        return response.ok
    except requests.RequestException as e:
        # Не логуємо сам e: текст винятку містить URL разом із токеном бота
        logging.error("Telegram %s error: %s", method, type(e).__name__)
        return False


def send_telegram(message, chat_id):
    return _post("sendMessage", 10, data={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    })


def send_photo(chat_id, image_bytes):
    return _post("sendPhoto", 20,
                 data={"chat_id": chat_id},
                 files={"photo": ("graph.png", image_bytes)})


def send_gif(chat_id, gif_url):
    return _post("sendAnimation", 20, data={
        "chat_id": chat_id,
        "animation": gif_url,
    })