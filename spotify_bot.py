import os
import re
import requests
import logging
from io import BytesIO
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- CONFIGURATION ---

# Fetch credentials from environment variables for security
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DOWNLOAD_API_KEY = os.environ.get("DOWNLOAD_API_KEY")

# API Endpoints
DOWNLOAD_API_ENDPOINT = "https://spotify-downloader12.p.rapidapi.com/convert"
DOWNLOAD_API_HOST = "spotify-downloader12.p.rapidapi.com"

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Regex to validate a Spotify track URL
SPOTIFY_URL_PATTERN = re.compile(
    r"https?://open\.spotify\.com/(track|album|playlist)/[a-zA-Z0-9]+(\?si=[a-zA-Z0-9]+)?(&nd=1)?"
)

# --- API Integration Layer ---

async def call_download_api(spotify_url: str) -> tuple[BytesIO | None, str | None]:
    """
    Calls the RapidAPI endpoint to fetch the music file.
    
    This is a 2-step process:
    1. POST to /convert to get an intermediate URL and payload.
    2. GET from the intermediate URL (with the payload) to get the file.
    """
    logger.info(f"Attempting API call for URL: {spotify_url}")

    # --- Step 1: Call RapidAPI to get the intermediate URL and payload ---
    querystring = {"urls": spotify_url}
    payload = {} 
    headers = {
        "x-rapidapi-key": DOWNLOAD_API_KEY,
        "x-rapidapi-host": DOWNLOAD_API_HOST,
        "Content-Type": "application/json"
    }

    try:
        # First request: Get the intermediate URL and payload
        api_response = requests.post(
            DOWNLOAD_API_ENDPOINT, 
            json=payload, 
            headers=headers, 
            params=querystring,
            timeout=30
        )
        api_response.raise_for_status()
        response_json = api_response.json()

        # --- Step 2: Parse the JSON and download the actual file ---
        if response_json.get('error') is True or not response_json.get('url'):
             logger.error(f"API Step 1 failed: {response_json.get('message', 'No error message')}")
             return None, None
            
        intermediate_url = response_json.get('url')
        intermediate_payload = response_json.get('payload')
        
        try:
            track_id = spotify_url.split('/')[-1].split('?')[0]
            track_name = f"Track_{track_id}"
        except Exception:
            track_name = "Downloaded_Track"

        if not intermediate_url or not intermediate_payload:
            logger.error(f"API response missing 'url' or 'payload'.")
            return None, None

        logger.info(f"API Step 1 success. Calling Step 2...")

        # The payload is a query parameter for a GET request.
        step_2_params = {
            'payload': intermediate_payload
        }

        # Second request: Download the actual MP3 file
        file_response = requests.get(
            intermediate_url,
            params=step_2_params,
            stream=True, 
            timeout=60
        )
        file_response.raise_for_status()
        
        file_content = file_response.content
        file_size_mb = len(file_content) / (1024 * 1024)
        logger.info(f"Downloaded file size: {file_size_mb:.2f} MB")

        if file_size_mb > 50:
            logger.error(f"File is too large for Telegram ({file_size_mb:.2f} MB). Max 50MB.")
            return None, None
            
        audio_file = BytesIO(file_content)
        audio_file.name = f"{track_name}.mp3"

        # Rewind the file to the beginning before sending
        audio_file.seek(0)
        
        logger.info(f"Successfully downloaded file: {audio_file.name}")
        return audio_file, track_name

    except requests.exceptions.Timeout:
        logger.error("API Call Error: The request timed out.")
        return None, None
    except requests.RequestException as e:
        logger.error(f"API Call Error: {e}")
        if e.response is not None:
             logger.error(f"API Response Code: {e.response.status_code}")
             logger.error(f"API Response Body: {e.response.text}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred in call_download_api: {e}")
        return None, None

# --- Telegram Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcoming message."""
    welcome_message = (
        "Hello! I am your Spotify Music Downloader Bot. 🎵\n\n"
        "Send me a direct Spotify track URL, and I will try to download the MP3 file for you."
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages, checking for a Spotify URL."""
    user_text = update.message.text
    if not user_text:
        return

    match = SPOTIFY_URL_PATTERN.search(user_text)
    if match:
        spotify_url = match.group(0)
        await process_spotify_link(update, context, spotify_url)
    else:
        await update.message.reply_text(
            "That doesn't look like a valid Spotify track URL. "
            "Please send a link that starts with `https://open.spotify.com/track/...`"
        )

async def process_spotify_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """Initiates the download process and sends the file."""
    
    status_message = await update.message.reply_text(
        "⏳ Connecting to download API and fetching track... This may take a moment."
    )
    
    audio_file, track_name = await call_download_api(url)
    
    if audio_file:
        try:
            # Send the audio file back to the user
            await update.message.reply_audio(
                audio=audio_file,
                caption=None,
                filename=f"{track_name}.mp3",
                parse_mode=None,
                # Give the upload 120 seconds (2 minutes) before timing out
                write_timeout=120
            )
            
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=status_message.message_id,
                text=f"✅ Download successful! Sending your audio file now."
            )

        except Exception as e:
            logger.error(f"Failed to send audio via Telegram: {e}")
            await update.message.reply_text(
                "❌ Error: I successfully downloaded the file but failed to upload it to Telegram. Please check the logs."
            )
        finally:
            audio_file.close()
    else:
        # Handle API failure
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=status_message.message_id,
            text=(
                "❌ Download Failed. The external API could not process the request "
                "or I failed to connect. This could be due to an invalid link, an API error, "
                "or the request timing out. Please try again later."
            )
        )

# --- Main Bot Setup ---

def main() -> None:
    """Starts the bot."""
    
    # --- Environment Variable Check ---
    if not TELEGRAM_TOKEN:
        logger.fatal("!!! FATAL ERROR: TELEGRAM_TOKEN environment variable not set. !!!")
        return
        
    if not DOWNLOAD_API_KEY:
        logger.fatal("!!! FATAL ERROR: DOWNLOAD_API_KEY environment variable not set. !!!")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot
    logger.info("Bot started successfully. Listening for commands...")
    application.run_polling(poll_interval=1.0)

if __name__ == '__main__':
    main()
