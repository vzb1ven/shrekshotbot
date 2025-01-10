import os
import time
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from PIL import Image
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Function to initialize the browser
def init_browser(driver_path):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode (no UI)
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=500,3000')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(service=Service(driver_path), options=options)
    return driver

# Function to capture a screenshot of a Telegram post
def capture_screenshot(link, driver):
    try:
        logging.info(f"Navigating to link: {link}")
        driver.get(link)
        time.sleep(5)  # Allow the page to load

        # Locate the specific Telegram post element
        element = driver.find_element(By.CLASS_NAME, 'tgme_widget_message_bubble')

        # Get element's location and size
        location = element.location
        size = element.size

        # Take a screenshot of the entire page
        screenshot = driver.get_screenshot_as_png()
        image = Image.open(BytesIO(screenshot))

        # Crop the image to the element
        left = location['x']
        top = location['y']
        right = left + size['width']
        bottom = top + size['height']
        cropped_image = image.crop((left, top, right, bottom))

        # Save the cropped screenshot to memory
        output = BytesIO()
        cropped_image.save(output, format='PNG')
        output.seek(0)
        logging.info("Screenshot captured successfully")
        return output

    except Exception as e:
        logging.error(f"Error capturing screenshot for {link}: {e}")
        return None

# Function to handle incoming messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # Check if this message has already been processed
    if context.chat_data.get("last_forwarded_id") == message.forward_origin.date:
        logging.info("Duplicate forwarded post detected; ignoring.")
        return

    # Store the last forwarded message ID to avoid duplicates
    context.chat_data["last_forwarded_id"] = message.forward_origin.date

    chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver/chromedriver")  # Configurable path

    # Initialize browser
    driver = init_browser(chromedriver_path)

    try:
        if message.forward_origin and message.forward_origin.type == "channel" and message.forward_origin.message_id:
            username = message.forward_origin.chat.username
            message_id = message.forward_origin.message_id
            reply_link = f"https://t.me/{username}/{message_id}/"
            link = f"https://t.me/{username}/{message_id}/?embed=1&mode=tme"

            logging.info(f"Processing forwarded channel post with link: {link}")

            # Capture the screenshot
            screenshot_stream = capture_screenshot(link, driver)

            if screenshot_stream:
                # Reply once with the screenshot
                await message.reply_photo(photo=screenshot_stream, caption=reply_link)
            else:
                await message.reply_text("Failed to capture the screenshot. Please try again.")
        else:
            await message.reply_text("This message is not a valid forwarded channel post.")

    finally:
        driver.quit()

if __name__ == "__main__":
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")  # Use environment variable for security

    if not bot_token:
        logging.error("Bot token is not set. Please set the TELEGRAM_BOT_TOKEN environment variable.")
        exit(1)

    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(MessageHandler(filters.FORWARDED, handle_message))

    logging.info("Bot is running...")
    app.run_polling()
