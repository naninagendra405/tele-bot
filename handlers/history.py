from telegram import Update
from telegram.ext import ContextTypes
from database.database import db
import datetime

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.datetime.now()
    one_hour_ago = now - datetime.timedelta(hours=0.5)
    bets = await db.get_bets_between(one_hour_ago, now, user_id)


    if not bets:
        await update.message.reply_text("🕘 No bets in the last hour.")
    else:
        msg = "🕘 Recent Bets:\n"
        for bet in bets:
            msg += f"• ₹{bet['amount']} on {bet['choice'].capitalize()} at {bet['timestamp'].strftime('%H:%M:%S')}\n"
        await update.message.reply_text(msg)
