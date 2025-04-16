from telegram import Update
from telegram.ext import ContextTypes
from database.database import db

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = await db.get_balance(user_id)
    await update.message.reply_text(f"💰 Your current balance is ₹{balance}")
