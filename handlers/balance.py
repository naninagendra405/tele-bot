from telegram import Update
from telegram.ext import ContextTypes
from database.database import db

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT balance, referral_balance, referral_count FROM users WHERE user_id = $1", user_id)
            if row:
                balance = row["balance"]
                referral_bonus = row["referral_balance"]
                referral_count = row["referral_count"]
                message = (
                    f"💰 Your Balance: ₹{balance:.2f}\n"
                    f"🎁 Total Referral Bonus: ₹{referral_bonus:.2f}\n"
                    f"👥 Total Referrals: {referral_count}"
                )
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("User not found.")
    except Exception as e:
        print(f"Error showing balance for user {user_id}: {e}")