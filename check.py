from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes, CallbackQueryHandler
)
import os
from dotenv import load_dotenv
import asyncio
import nest_asyncio

# Custom imports
from database.database import db
from handlers.results import start_result_processing
from handlers.admin import handle_approve_callback
from handlers.balance import show_balance
from handlers.history import show_history
from handlers.service import show_service
from config import ADMIN_ID

# Enable nested event loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Define conversation states
(DEPOSIT_TXN_ID, DEPOSIT_AMOUNT,
 WITHDRAW_UPI_ID, WITHDRAW_AMOUNT,
 BET_ENTER_AMOUNT, BET_CHOOSE_SIDE) = range(6)

# 🧭 Main Menu Keyboard
def main_menu():
    keyboard = [["🎯 Place a Bet"],
                ["📥 Deposit", "📤 Withdraw"],
                ["💰 Balance", "🕘 History"],
                ["🛠 Service"],
                [KeyboardButton("/start")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# 🟢 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await db.ensure_user(user_id) 
    keyboard = [["🎯 Place a Bet"],
                ["📥 Deposit", "📤 Withdraw"],
                ["💰 Balance", "🕘 History"],
                ["🛠 Service"]]

    if user_id == ADMIN_ID:
        keyboard.append(["🔐 Admin"])

    await update.message.reply_text("👋 Welcome! Choose an option:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏁 Process cancelled. Back to main menu.", reply_markup=main_menu())
    return ConversationHandler.END

# Show Admin Panel
async def show_admin_controls(update, context):
    if update.effective_user.id != 1090201656:
        return

    keyboard = ReplyKeyboardMarkup([
        ["✅ Approve Deposits", "💸 Approve Withdrawals"],
        ["👥 View Users & Balances", "📊 View Admin Profit"],
        ["🕒 View Recent Bets"],
        ["🔙 Back to Menu"]
    ], resize_keyboard=True)

    await update.message.reply_text("🔐 Admin Control Panel", reply_markup=keyboard)

# Show pending deposits (admin only)
async def show_pending_deposits(update, context):
    if update.effective_user.id != 1090201656:
        return

    deposits = await db.get_pending_deposits()
    if not deposits:
        await update.message.reply_text("No pending deposits.")
        return

    for deposit in deposits:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{deposit['id']}")
        ]])
        await update.message.reply_text(
            f"User ID: {deposit['user_id']}\nAmount: ₹{deposit['amount']}\nTxn ID: {deposit['transaction_id']}",
            reply_markup=keyboard
        )

async def show_pending_withdrawals(update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    withdrawals = await db.get_pending_withdrawals()
    if not withdrawals:
        await update.message.reply_text("No pending withdrawals.")
        return

    for wd in withdrawals:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"approve_withdraw_{wd['id']}")]])
        await update.message.reply_text(
            f"User ID: {wd['user_id']}\nAmount: ₹{wd['amount']}\nUPI: {wd['upi_id']}",
            reply_markup=keyboard
        )


# Handle the callback when admin clicks "Approve"
async def handle_approve_callback(update, context):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("approve_"):
        data = query.data.split("_")
        if data[1] == "withdraw":
            withdrawal_id = int(data[2])
            await db.approve_withdrawal(withdrawal_id)
            await query.edit_message_text("✅ Withdrawal approved and balance updated.")
        else:
            deposit_id = int(data[1])
            await db.approve_deposit(deposit_id)
            await query.edit_message_text("✅ Deposit approved and user balance updated.")


async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return

    users = await db.get_all_users_and_balances()
    if not users:
        await update.message.reply_text("No users found.")
        return

    msg = "👥 All Users & Balances:\n\n"
    for row in users:
        msg += f"🧑 User ID: {row['user_id']} | 💰 Balance: ₹{row['balance']}\n"

    await update.message.reply_text(msg)

async def show_admin_profit(update, context):
    if update.effective_user.id != 1090201656:
        return

    profit = await db.get_admin_profit()
    await update.message.reply_text(f"📊 Total Admin Profit: ₹{profit}")

async def show_recent_bets(update, context):
    if update.effective_user.id != 1090201656:
        return

    bets = await db.get_recent_bets()
    if not bets:
        await update.message.reply_text("No recent bets in the last hour.")
        return

    msg = "🕒 Recent Bets:\n"
    for bet in bets:
        msg += f"🆔 {bet['user_id']} — ₹{bet['amount']} on {bet['choice']} ({bet['timestamp']})\n"
    await update.message.reply_text(msg)



# -------------------- 🎯 BETTING --------------------
async def start_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 How much do you want to bet?", reply_markup=ReplyKeyboardRemove())
    return BET_ENTER_AMOUNT

async def receive_bet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    amount_text = update.message.text.strip()

    if not amount_text.isdigit():
        await update.message.reply_text("❗ Please enter a valid number.")
        return BET_ENTER_AMOUNT

    amount = int(amount_text)
    balance = await db.get_balance(user.id)

    if amount > balance:
        await update.message.reply_text("❌ Insufficient balance.")
        return ConversationHandler.END

    context.user_data['bet_amount'] = amount
    keyboard = [[KeyboardButton("Heads")], [KeyboardButton("Tails")]]
    await update.message.reply_text(
        "Choose your side:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return BET_CHOOSE_SIDE

async def receive_bet_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    if choice not in ["heads", "tails"]:
        await update.message.reply_text("❗ Please choose either Heads or Tails.")
        return BET_CHOOSE_SIDE

    user = update.effective_user
    amount = context.user_data.get("bet_amount")
    balance = await db.get_balance(user.id)

    if balance < amount:
        await update.message.reply_text("❌ Insufficient balance.")
        return ConversationHandler.END

    await db.add_bet(user.id, amount, choice)
    await db.update_balance(user.id, -amount)

    await update.message.reply_text(
        f"✅ Bet placed: ₹{amount} on {choice.capitalize()}.Remaining: ₹{balance - amount}",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

# -------------------- 📥 DEPOSIT --------------------
# -------------------- 💰 DEPOSIT (RAZORPAY) --------------------

async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧾 To deposit, please send the amount to our Razorpay link:\n"
        "🔗 [Click here to Pay](https://razorpay.me/@noadvance)\n\n"
        "💡 After payment, you'll receive a **Payment ID** like `pay_XXXXXXXXXXXXXX`. "
        "Please enter it below for verification.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return DEPOSIT_TXN_ID

async def receive_transaction_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txn_id = update.message.text.strip()

    if not (txn_id.startswith("pay_") and len(txn_id) == 18):
        await update.message.reply_text("❌ Invalid Razorpay Payment ID. It must start with `pay_` and be 18 characters long.")
        return DEPOSIT_TXN_ID

    context.user_data["txn_id"] = txn_id
    await update.message.reply_text("💵 How much did you deposit?")
    return DEPOSIT_AMOUNT

async def receive_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    amount_text = update.message.text.strip()

    if not amount_text.isdigit():
        await update.message.reply_text("❗ Please enter a valid number.")
        return DEPOSIT_AMOUNT

    amount = int(amount_text)
    txn_id = context.user_data.get("txn_id")

    await db.record_deposit(user.id, txn_id, amount)

    await update.message.reply_text(
        f"✅ ₹{amount} has been submitted for verification with Payment ID `{txn_id}`.\n"
        f"⏳ It will be approved shortly.",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    return ConversationHandler.END


# -------------------- 📤 WITHDRAW --------------------
# ---- Step 1: Ask for amount first ----
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💸 How much do you want to withdraw?", reply_markup=ReplyKeyboardRemove())
    return WITHDRAW_AMOUNT

# ---- Step 2: Validate amount before asking for UPI ----
async def receive_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    amount_text = update.message.text.strip()

    if not amount_text.isdigit():
        await update.message.reply_text("❗ Please enter a valid number.")
        return WITHDRAW_AMOUNT

    amount = int(amount_text)
    balance = await db.get_balance(user.id)

    if amount > balance:
        await update.message.reply_text("❌ Insufficient balance. Your current balance is ₹{}.".format(balance))
        return ConversationHandler.END

    context.user_data["withdraw_amount"] = amount
    await update.message.reply_text("💳 Enter your UPI ID for withdrawal:")
    return WITHDRAW_UPI_ID

# ---- Step 3: Take UPI ID and record withdrawal ----
async def receive_withdraw_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upi_id = update.message.text.strip()
    amount = context.user_data.get("withdraw_amount")

    await db.record_withdrawal(user.id, upi_id, amount)
    await db.update_balance(user.id, -amount)

    await update.message.reply_text(
        f"✅ Withdrawal request for ₹{amount} to UPI ID `{upi_id}` submitted.",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    return ConversationHandler.END


# -------------------- 🤖 BOT INIT --------------------
async def main():
    await db.connect()
    print("✅ Connected to the database.")

    app = Application.builder().token(TOKEN).build()

    # Command and message handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Start$"), start))
    app.add_handler(MessageHandler(filters.Text("🔐 Admin"), show_admin_controls))
    app.add_handler(MessageHandler(filters.Text("👥 Users & Balances"), show_all_users))
    app.add_handler(MessageHandler(filters.Text("💰 Balance"), show_balance))
    app.add_handler(MessageHandler(filters.Text("🕘 History"), show_history))
    app.add_handler(MessageHandler(filters.Text("🛠 Service"), show_service))
    app.add_handler(CommandHandler("approve_deposits", show_pending_deposits))
    app.add_handler(CommandHandler("admin", show_admin_controls))

    # Admin panel handlers
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^✅ Approve Deposits$"), show_pending_deposits))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💸 Approve Withdrawals$"), show_pending_withdrawals))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^👥 View Users & Balances$"), show_all_users))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📊 View Admin Profit$"), show_admin_profit))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🕒 View Recent Bets$"), show_recent_bets))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔙 Back to Menu$"), start))

    

    # Deposit
    app.add_handler(CallbackQueryHandler(handle_approve_callback))
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Text("📥 Deposit"), deposit_start)],
        states={
            DEPOSIT_TXN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_transaction_id)],
            DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deposit_amount)],
        },
        fallbacks=[MessageHandler(filters.Text("🏠 Start"), cancel)],
    ))

    # Withdraw
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Text("📤 Withdraw"), withdraw_start)],
        states={
            WITHDRAW_UPI_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_amount)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_upi)],
        },
        fallbacks=[MessageHandler(filters.Text("🏠 Start"), cancel)],
    ))

    # Bet
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Text("🎯 Place a Bet"), start_bet)],
        states={
            BET_ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bet_amount)],
            BET_CHOOSE_SIDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bet_choice)],
        },
        fallbacks=[MessageHandler(filters.Text("🏠 Start"), cancel)],
    ))

    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
