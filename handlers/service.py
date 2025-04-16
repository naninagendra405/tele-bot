from telegram import Update
from telegram.ext import ContextTypes

async def show_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛠 For any help, contact support at @YourSupportUsername")
