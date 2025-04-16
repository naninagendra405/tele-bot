from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Place a Bet")],
            [KeyboardButton(text="📥 Deposit"), KeyboardButton(text="📤 Withdraw")],
            [KeyboardButton(text="📊 Balance"), KeyboardButton(text="🕘 History")],
            [KeyboardButton(text="💬 Service")]
        ],
        resize_keyboard=True
    )
