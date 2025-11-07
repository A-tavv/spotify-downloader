# S_Botify - Spotify Downloader Telegram Bot

A simple, robust, and deployable Telegram bot named S_Botify that downloads Spotify tracks directly from a URL.

This bot uses Python's python-telegram-bot library, connects to a third-party RapidAPI for file processing, and is configured for 24/7 cloud deployment.

## How to Use

Using the bot is simple:

Find S_Botify on Telegram. (@downloadbyspotify_bot)

Send the bot a valid Spotify track URL (e.g., https://open.spotify.com/track/...).

The bot will process the link and send you the MP3 audio file back.

## Bot Architecture

This bot is designed to be a lightweight and scalable service.

Bot Logic (spotify_bot.py): A single Python script handles all bot interactions. It uses asyncio via the python-telegram-bot library to handle multiple user requests efficiently.

API Integration: The bot does not process music itself. It securely forwards requests to an external RapidAPI (spotify-downloader12) to get the audio file.

Error Handling: The bot is built to be robust, catching API failures, download timeouts, and upload timeouts, and reporting a clean failure message to the user instead of crashing.


## Deployment

This bot is built to run 24/7 on a cloud platform (Railway). The repository includes the necessary files for a seamless deployment:

spotify_bot.py: The main application logic.

requirements.txt: Specifies the exact Python dependencies (python-telegram-bot, requests).

runtime.txt: Locks the deployment to a stable Python version (python-3.11) to prevent version-related crashes.

Environment Variables

For security and portability, the bot is configured to read secrets from environment variables. To run this bot, you must set the following on your server:

TELEGRAM_TOKEN: Your unique token from Telegram's @BotFather.

DOWNLOAD_API_KEY: Your API key for the spotify-downloader12 RapidAPI.
