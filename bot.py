import logging
import os

from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot

from firebase_admin import credentials, initialize_app
from firebase_admin import db

import requests

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# Telegram bot init
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
bot = Bot(token=TELEGRAM_BOT_TOKEN) 
# TODO - get it automatic - get it in the /start command using await and async
chat_id = 688103792
dp = updater.dispatcher


# Firebase init
cred = credentials.Certificate(
    "telebot-robophone-firebase-adminsdk-5ugar-c768152848.json")
initialize_app(cred, {
    'databaseURL': 'https://telebot-robophone-default-rtdb.europe-west1.firebasedatabase.app/'
})
ref = db.reference("Robophone/")


def vaildate_phone_number(number: str):
    """Returns a valid IL number for example: +972501234567"""
    res = number
    COUNTRY_CODE_IL = "+972"

    if '-' in number:
        res = number.replace('-', '')

    n = len(number)
    print("number:", number)
    if n <= 10:
        if number[0] == 0 and n == 10:
            res = COUNTRY_CODE_IL + res[1:]
        else:
            res = COUNTRY_CODE_IL + res
    return res


def markup_inline():
    """Creating buttons"""
    buttons = [InlineKeyboardButton("Ignore", callback_data="ignore"),
               InlineKeyboardButton("Call The Police!🚔",
                                    callback_data='police'),
               InlineKeyboardButton("Turn on the Alert🚨",
                                    callback_data='alert'),
               InlineKeyboardButton("Message my Neighbor📤",
                                    callback_data='message'),
               InlineKeyboardButton("It's Ok, it's the weather. Ignore.🍃", callback_data='ignore')]
    buttons_rows = [buttons[i:i + 1]
                    for i in range(0, len(buttons))]  # converting columns to rows
    markup = InlineKeyboardMarkup(buttons_rows)
    return markup


def start(update, context):
    """Start the conversation and shows the user all the options."""
    first_name = update.message.chat.first_name
    global chat_id
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Hi {}!\nUse /set_emergency_phone to set emergency contact.\n/security_on to turn on the system.\n/security_off to turn off the system.".format(first_name))
    ref.update({"user_first_name": first_name})


def get_weather_data():
    WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")  # NOTE - Expires in 24/02/2023
    API_ENDPOINT = "https://api.weatherapi.com/v1/forecast.json"
    PARAMS = {"key": WEATHER_API_KEY,
              "q": "Haifa",
              "days": 2,
              "aqi": "no",
              "alerts": "no"}
    return requests.get(API_ENDPOINT, PARAMS).json()


def set_emergency_phone(update, context):
    """Asks user to send a contact"""
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Please send me a contact:")


# TODO - make sure it works good
def set_emergency_phone_contact(update, context):
    """Updates emergency contact name and phone number."""
    contact = update.message.contact
    phone_number = vaildate_phone_number(contact.phone_number)
    first_name = update.message.contact.first_name
    print("phone_number:", phone_number)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Setting emergency contact number to: {}".format(phone_number))
    ref.update({"contact_number": phone_number, "contact_name": first_name})
    print("Updating contact number to -> {}".format(phone_number))
    logger.info("Emergency contact - %s: %s", first_name, phone_number)


def set_security_on(update, context):
    """Sets security system to active"""
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Setting Security On!")
    ref.update({"status": "ON", "day_sim": "OFF"})
    print("Updating status -> ON")
    logger.info("Updating status to ON")


def set_security_off(update, context):
    """Sets security system to inactive"""
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Setting Security Off!")
    ref.update({"status": "OFF"})
    print("Updating status -> OFF")
    logger.info("Updating status to OFF")


def day_simulation(update, context):
    ref.update({"day_sim": "ON", "status": "OFF"})
    print("Updating day_sim -> ON")
    logger.info("Updating day_sim: ON")


def ignore_handle():
    ref.update({"Action": "ignore"})
    print("updating Action to ignore")


def police_handle():
    ref.update({"Action": "police"})
    print("updating Action to police")


def alert_handle():
    ref.update({"Action": "alert"})
    print("updating Action to alert")


def message_handle():
    ref.update({"Action": "message"})
    print("updating Action to message")


def button_callback(update: Update, context) -> None:
    """Parses the CallbackQuery, calls the relevant fucntion and updates the message text."""
    query = update.callback_query
    query.answer()
    map_actions = {"ignore": ignore_handle,
                   "police": police_handle,
                   "alert": alert_handle,
                   "message": message_handle}
    map_actions[query.data]()  # call handle function
    query.edit_message_text(text=f"Selected option: {query.data}")
    # turning off the alarm after handling it, turning off the system
    ref.update({"Alarm": "OFF", "status": "OFF"})
    bot.send_message(update.effective_chat.id,
                     text="Watch out! Now the security system is off, if you want to reactivate it please select: /security_on")


def get_weather_status():
    weather_data = get_weather_data()
    current_wind_kph = weather_data["current"]["wind_kph"]
    if current_wind_kph <= 20:  # TODO - cast to a num?
        status = "Good Weather."
    else:
        status = "Bad weather, Very High speed wind!"
    return status, current_wind_kph


def firebase_callback(event):
    """Callback function when a value is changed in the db"""
    print("Firebase callback function")
    weather_status, wind_kph = get_weather_status()
    print("path:", event.path)
    print(":", event.data)
    if event.path == "/Alarm" and event.data == "ON":
        # Security alarm is on
        bot.send_message(
            chat_id=chat_id, text="OMG! Something suspicious is happening near your house!")
        bot.send_message(chat_id=chat_id, text="Weather status: %s Wind speed: %s [kph]" % (
            weather_status, wind_kph))
        bot.send_message(
            chat_id=chat_id, text="Please choose how to handle it:", reply_markup=markup_inline())
        dp.add_handler(CallbackQueryHandler(button_callback))
    if event.path == "/is_family_member":
        # Disable all security - we are safe, someone valid is home.
        if event.data == "ON":
            bot.send_message(
                chat_id=chat_id, text="A family member is in the house - you can relax and turn off the security system using /security_off.")

        elif event.data == "ON_2":
            bot.send_message(
                chat_id=chat_id, text="Hi, a family member just got into the house.")


def main():
    """Run the bot."""
    print("Running the bot")

    # Add db listener to changes of firebase db value
    db.reference('Robophone/').listen(firebase_callback)

    # Add conversation handler with the states set_emergency_phone, security_on and security_off
    dp.add_handler(CommandHandler("start", start))
    # dp.add_handler(CommandHandler("weather", weather_callback))
    dp.add_handler(CommandHandler("set_emergency_phone", set_emergency_phone))
    dp.add_handler(MessageHandler(
        filters.Filters.contact, set_emergency_phone_contact))
    dp.add_handler(CommandHandler("security_on", set_security_on))
    dp.add_handler(CommandHandler("security_off", set_security_off))
    dp.add_handler(CommandHandler("day_simulation", day_simulation))

    # Run the bot
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
