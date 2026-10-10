import logging
import requests

from config import CR_TOKEN, CR_PROXY_BASE, HTTP_TIMEOUT


def _headers():
    return {"Authorization": f"Bearer {CR_TOKEN}"} if CR_TOKEN else {}


def _normalize_tag(tag):
    return tag.replace("#", "").upper()


def _get(path):
    url = f"{CR_PROXY_BASE}{path}"
    try:
        logging.info("REQUEST → %s", url)
        response = requests.get(url, headers=_headers(), timeout=HTTP_TIMEOUT)
        logging.info("RESPONSE → %s", response.status_code)

        if response.status_code == 200:
            return response.json()

        logging.error("%s | Proxy error: %s | %s", path, response.status_code, response.text)
    except (requests.RequestException, ValueError) as e:
        logging.error("Proxy request failed: %s", e)
    return None


def get_battle_log(player_tag):
    data = _get(f"/players/%23{_normalize_tag(player_tag)}/battlelog")
    return data or []


def get_player_name(player_tag):
    data = _get(f"/players/%23{_normalize_tag(player_tag)}")
    return data.get("name") if data else None