from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from database.database import db

# Set your actual admin Telegram ID here
ADMIN_ID = 1090201656

# Helper decorator to restrict access
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
        return await func(update, context)
    return wrapper

# --- View Bet Summary ---
@admin_only
async def view_bet_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = await db.get_bet_summary()
    msg = "📊 *Bet Summary (Last 30 minutes)*:\n\n"
    for side, data in summary.items():
        msg += f"*{side}* - ₹{data['total_amount'] or 0} from {data['num_bets']} users\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- Accept Result: Ask Winning Side ---
@admin_only
async def accept_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(
        [["Heads", "Tails"], ["🔙 Back to Menu"]],
        resize_keyboard=True
    )
    await update.message.reply_text("✅ Select the *winning side*:", reply_markup=keyboard, parse_mode="Markdown")
    return "AWAITING_RESULT_CHOICE"

# --- Handle Final Choice & Notify Users ---
@admin_only
async def handle_result_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()

    # Check if the user selected a new option from the main menu
    if choice == "🔙 Back to Menu":
        await update.message.reply_text("🔙 Returning to the main menu.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if choice not in ["Heads", "Tails"]:
        await update.message.reply_text("❌ Invalid choice. Please choose Heads or Tails.")
        return "AWAITING_RESULT_CHOICE"

    # Approve result and get winner/loser lists
    winners, losers = await db.approve_result(choice)

    # Notify winners
    for user_id, amount in winners:
        try:
            await context.bot.send_message(user_id, f"🎉 You WON ₹{amount * 2}! ({choice})")
        except Exception:
            pass  # User might have blocked the bot

    # Notify losers
    for user_id, amount in losers:
        try:
            await context.bot.send_message(user_id, f"❌ You LOST ₹{amount}. Better luck next time!")
        except Exception:
            pass

    # Reset the bet summary
    await db.clear_all_bets()

    await update.message.reply_text(
        f"🎯 *Result Approved!*\n\n🏆 Winning Side: *{choice}*\n"
        f"🎉 Winners: {len(winners)}\n💸 Losers: {len(losers)}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Admin Result Handler Setup
admin_result_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("✅ Accept Result"), accept_result)],
    states={
        "AWAITING_RESULT_CHOICE": [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_result_choice)
        ]
    },
    fallbacks=[MessageHandler(filters.Regex("🔙 Back to Menu"), accept_result)],
    per_user=True,
)