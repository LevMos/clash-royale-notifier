🎮 Clash Royale Battle Notifier

Clash Royale Battle Notifier is a Telegram bot written in Python that monitors a specific player in Clash Royale and sends battle notifications in real time.

The bot tracks trophies, win streaks, daily statistics, and can automatically send a daily summary at midnight (GMT).

This project demonstrates working with external APIs, background jobs, logging, and cloud deployment.

🚀 Features

🔍 Monitors player battle log via Clash Royale Developer API
📩 Sends formatted Telegram notifications for each new battle
🏆 Shows trophy change and total trophies
🔥 Tracks win streak
📊 Generates daily player statistics
🌙 Automatically sends daily summary at 00:00 GMT
🎞 Can send GIFs for good / bad days
☁ Ready for deployment on Render

🛠 Technologies Used

Python 3
requests
python-dotenv
Telegram Bot API
Clash Royale Developer API
Supabase (optional, for persistence)
APScheduler (for daily tasks)

🔑 Setup Guide

1️⃣ Clone repository
git clone https://github.com/LevMos/clash-royale-notifier.git
cd clash-royale-notifier

2️⃣ Create virtual environment
python3 -m venv venv
source venv/bin/activate
(Windows: venv\Scripts\activate)

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Configure environment variables
Create .env file:

CR_TOKEN=your_clash_api_token
TG_TOKEN=your_telegram_bot_token
CHAT_ID=your_chat_id
PLAYER_TAG=%23PLAYER_TAG
CHECK_INTERVAL=120

Make sure your Clash Royale API key has the correct public IP whitelisted.

▶ Running the Bot
python Backend/main.py

The bot checks battles every CHECK_INTERVAL seconds and sends a Telegram message when a new battle appears.

If scheduler is enabled, it will also send a daily statistics message at midnight (GMT).

⚠ Important Notes

Clash Royale API keys work only with whitelisted public IPs
The bot detects new battles (not live matches)
Never commit your .env file
If your server IP changes (Render), update it in the Clash Developer Portal

📄 License
MIT License
