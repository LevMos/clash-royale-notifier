import requests
import os

API_TOKEN = os.getenv("CLASH_API_TOKEN")
PLAYER_TAG = os.getenv("PLAYER_TAG")

def get_last_battle():
    url = f"https://api.clashroyale.com/v1/players/%23{PLAYER_TAG}/battlelog"

    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }

    response = requests.get(url, headers=headers)
    data = response.json()

    if not data:
        return None

    battle = data[0]

    team = battle["team"][0]["crowns"]
    opponent = battle["opponent"][0]["crowns"]

    if team > opponent:
        result = "win"
    elif team < opponent:
        result = "loss"
    else:
        result = "draw"

    return battle["battleTime"], result