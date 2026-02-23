# 🎮 Clash Royale Online Notifier

Clash Royale Online Notifier is a simple Telegram bot written in Python that monitors a specific player in Clash Royale and sends a notification when a new battle appears in the player's battle log.

This project was created as a minimal, clean, and GitHub-ready mini backend project. It demonstrates working with external APIs, environment variables, logging, and basic automation.

---

## 🚀 Features

- Checks player battle log using the official Clash Royale Developer API
- Sends Telegram notification when a new battle is detected
- Uses environment variables (.env) to protect sensitive data
- Simple and clean project structure
- Ready to be deployed locally or extended further

---

## 🛠 Technologies Used

- Python 3
- requests
- python-dotenv
- Telegram Bot API
- Clash Royale Developer API

---

## 📦 Project Structure

clash-royale-notifier/
│
├── bot.py
├── .env.example
├── requirements.txt
├── README.md
└── .gitignore

---

## 🔑 Setup Guide

### 1. Clone the repository

git clone https://github.com/LevMos/clash-royale-notifier.git  
cd clash-royale-notifier  

### 2. Create a virtual environment

python3 -m venv venv  
source venv/bin/activate  

(On Windows use: venv\Scripts\activate)

### 3. Install dependencies

pip install -r requirements.txt  

### 4. Configure environment variables

Create a `.env` file in the root directory and add the following variables:

CR_TOKEN=your_clash_api_token  
TG_TOKEN=your_telegram_bot_token  
CHAT_ID=your_chat_id  
PLAYER_TAG=%23PLAYER_TAG  
CHECK_INTERVAL=120  

Make sure your Clash Royale API key is configured with the correct public IP address of the machine running the bot.

---

## ▶ Running the Bot

Activate your virtual environment and run:

python bot.py  

The bot will check the player's battle log every 120 seconds (or the value set in CHECK_INTERVAL) and send a Telegram message if a new battle is detected.

---

## ⚠ Important Notes

- The Clash Royale API key works only from whitelisted public IP addresses.
- The bot detects new battles, not real-time online status.
- Never commit your .env file to GitHub.
- If your public IP changes, you must update it in the Clash Royale Developer Portal.

---

## 📄 License

This project is licensed under the MIT License.
