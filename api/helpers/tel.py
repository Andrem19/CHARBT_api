import os
from decouple import config
from telegram import Bot

async def send_inform_message(message, image_path: str, send_pic: bool):
    try:
        CHAT_ID=851925585
        api_token = config("TELEGRAM_API")
        
        bot = Bot(token=api_token)

        response = None
        if send_pic:
            with open(image_path, 'rb') as photo:
                response = await bot.send_photo(chat_id=CHAT_ID, photo=photo, caption=message)
        else:
            response = await bot.send_message(chat_id=CHAT_ID, text=message)

        if response:
            print("Inform message sent successfully!")
        else:
            print("Failed to send inform message.")
    except Exception as e:
        print("An error occurred:", str(e))