from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackQueryHandler)
import os
from database.database import db
from handlers import admin_result
from handlers.balance import show_balance
from handlers.history import show_history
from handlers.service import show_service
from config import ADMIN_ID
from dotenv import load_dotenv
import nest_asyncio

# Enable nested event loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Define conversation states
(DEPOSIT_AMOUNT, DEPOSIT_TXN_ID, WITHDRAW_AMOUNT, WITHDRAW_UPI_ID, BET_ENTER_AMOUNT, BET_CHOOSE_SIDE) = range(6)

# 🧭 Main Menu Keyboard
def main_menu():
    keyboard = [
        ["🎯 Place a Bet"],
        ["📥 Deposit", "📤 Withdraw"],
        ["💰 Balance", "🕘 History"],
        ["🛠 Service"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# 🟢 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()  # Clear previous data
        user_id = update.effective_user.id
        full_name = update.effective_user.full_name

        # Debugging output
        print(f"User {full_name} with ID {user_id} started the bot.")

        # Register user without referral logic
        is_new = await db.add_user(user_id, full_name)
        print(f"User registration status: {'New user added' if is_new else 'User already exists'}")

        # Convert the keyboard to a list to allow appending
        keyboard = main_menu().keyboard
        keyboard = list(keyboard)  # Convert tuple to list

        if user_id == ADMIN_ID:
            keyboard.append(["🔐 Admin"])

        await update.message.reply_text(
            "👋 Welcome! Choose an option:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
    except Exception as e:
        print(f"Error in /start command: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Process cancelled.",
            reply_markup=main_menu()
        )
    except Exception as e:
        print(f"Error in cancel command: {e}")
    return ConversationHandler.END

# Show Admin Panel
async def show_admin_controls(update, context):
    try:
        context.user_data.clear()  # Clear previous data
        user_id = update.effective_user.id

        # Debugging output
        print(f"Admin panel accessed by user ID {user_id}")

        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized.")
            return

        keyboard = ReplyKeyboardMarkup([
            ["✅ Approve Deposits", "💸 Approve Withdrawals"],
            ["👥 View Users & Balances", "📊 View Admin Profit"],
            ["🕒 View Recent Bets", "🧮 View Bet Summary"],
            ["✅ Accept Result"],
            ["🔙 Back to Menu"]
        ], resize_keyboard=True)

        await update.message.reply_text("🔐 Admin Control Panel", reply_markup=keyboard)
    except Exception as e:
        print(f"Error in show_admin_controls: {e}")

# Show pending deposits (admin only)
async def show_pending_deposits(update, context):
    try:
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized.")
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
    except Exception as e:
        print(f"Error in show_pending_deposits: {e}")

async def show_pending_withdrawals(update, context):
    try:
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized.")
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
    except Exception as e:
        print(f"Error in show_pending_withdrawals: {e}")

# Handle the callback when admin clicks "Approve"
async def handle_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        data = query.data.split("_")

        if len(data) < 2:
            return await query.edit_message_text("❌ Invalid action.")

        action = data[0]
        type_or_id = data[1]

        if action != "approve":
            return

        if type_or_id == "withdraw":
            # approve_withdraw_123
            withdrawal_id = int(data[2])
            await db.approve_withdrawal(withdrawal_id)
            await query.edit_message_text("✅ Withdrawal approved and balance updated.")
        else:
            # approve_123 (deposit)
            deposit_id = int(type_or_id)
            await db.approve_deposit(deposit_id)
            await query.edit_message_text("✅ Deposit approved and user balance updated.")
    except Exception as e:
        print(f"Error in handle_approve_callback: {e}")

async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        print(f"Error in show_all_users: {e}")

async def show_admin_profit(update, context):
    try:
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized.")
            return

        profit = await db.get_admin_profit()
        await update.message.reply_text(f"📊 Total Admin Profit: ₹{profit}")
    except Exception as e:
        print(f"Error in show_admin_profit: {e}")

async def show_recent_bets(update, context):
    try:
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized.")
            return

        bets = await db.get_recent_bets()
        if not bets:
            await update.message.reply_text("No recent bets in the last hour.")
            return

        msg = "🕒 Recent Bets:\n"
        for bet in bets:
            msg += f"🆔 {bet['user_id']} — ₹{bet['amount']} on {bet['choice']} ({bet['timestamp']})\n"
        await update.message.reply_text(msg)
    except Exception as e:
        print(f"Error in show_recent_bets: {e}")

# -------------------- 🎯 BETTING --------------------

async def bet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()  # Clear previous data
        await update.message.reply_text(
            "💰 Please enter the amount you want to bet:",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        print(f"Error in bet_start: {e}")
    return BET_ENTER_AMOUNT

async def bet_enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()

        # Check if the user selected a new option from the main menu
        if text == "🎯 Place a Bet":
            return BET_ENTER_AMOUNT
        elif text == "📥 Deposit":
            await deposit_start(update, context)
            return ConversationHandler.END
        elif text == "📤 Withdraw":
            await withdraw_start(update, context)
            return ConversationHandler.END
        elif text in ["💰 Balance", "🕘 History", "🛠 Service"]:
            await start(update, context)
            return ConversationHandler.END

        if not text.isdigit():
            await update.message.reply_text("❗ Please enter a valid number.")
            return BET_ENTER_AMOUNT

        amount = int(text)
        user = update.effective_user

        # Check if the user has enough balance
        balance = await db.get_balance(user.id)
        if amount > balance:
            await update.message.reply_text("❌ Insufficient balance. Please enter a valid bet amount.")
            return BET_ENTER_AMOUNT

        context.user_data["bet_amount"] = amount

        # Ask for Heads or Tails
        keyboard = [["Heads", "Tails"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🔮 Choose your side: Heads or Tails?",
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error in bet_enter_amount: {e}")
    return BET_CHOOSE_SIDE

async def bet_choose_side(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()

        # Check if the user selected a new option from the main menu
        if text == "🎯 Place a Bet":
            await bet_start(update, context)
            return ConversationHandler.END
        elif text == "📥 Deposit":
            await deposit_start(update, context)
            return ConversationHandler.END
        elif text == "📤 Withdraw":
            await withdraw_start(update, context)
            return ConversationHandler.END
        elif text in ["💰 Balance", "🕘 History", "🛠 Service"]:
            await start(update, context)
            return ConversationHandler.END

        if text not in ["Heads", "Tails"]:
            await update.message.reply_text("❗ Please choose either Heads or Tails.")
            return BET_CHOOSE_SIDE

        amount = context.user_data["bet_amount"]
        user = update.effective_user

        # Store the bet in the database
        await db.record_bet(user.id, amount, text)

        # Deduct the bet amount from the user's balance
        await db.update_balance(user.id, -amount)

        # Send confirmation message to the user
        await update.message.reply_text(
            f"✅ Your bet of ₹{amount} on {text} has been placed successfully.",
            reply_markup=main_menu()
        )
    except Exception as e:
        print(f"Error in bet_choose_side: {e}")
    return ConversationHandler.END

# -------------------- 📥 DEPOSIT --------------------
# -------------------- 💰 DEPOSIT (RAZORPAY) --------------------

# Step 1: Ask for deposit amount
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()  # Clear previous data
        await update.message.reply_text("💵 How much would you like to deposit?    Min ₹50", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        print(f"Error in deposit_start: {e}")
    return DEPOSIT_AMOUNT

# Step 2: Validate deposit amount and show payment link
async def receive_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()

        # Check if the user selected a new option from the main menu
        if text == "🎯 Place a Bet":
            await bet_start(update, context)
            return ConversationHandler.END
        elif text == "📥 Deposit":
            return DEPOSIT_AMOUNT
        elif text == "📤 Withdraw":
            await withdraw_start(update, context)
            return ConversationHandler.END
        elif text in ["💰 Balance", "🕘 History", "🛠 Service"]:
            await start(update, context)
            return ConversationHandler.END

        if not text.isdigit():
            await update.message.reply_text("❗ Please enter a valid number.")
            return DEPOSIT_AMOUNT

        amount = int(text)
        if amount < 50:
            await update.message.reply_text("⚠️ Minimum deposit amount is ₹50. Please enter a higher amount.")
            return DEPOSIT_AMOUNT

        context.user_data["deposit_amount"] = amount

        # Ensure proper Markdown formatting
        message = (
            f"🧾 Please send ₹{amount} to our Razorpay link:\n"
            f"🔗 [Click here to Pay](https://razorpay.me/@noadvance)\n\n"
            "💡 After payment, you'll receive a **Payment ID** like `pay_XXXXXXXXXXXXXX`. "
            "Please enter it below for verification."
        )

        await update.message.reply_text(
            message,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error in receive_deposit_amount: {e}")
    return DEPOSIT_TXN_ID

# Step 3: Validate transaction ID and store in DB
async def receive_transaction_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()

        # Check if the user selected a new option from the main menu
        if text == "🎯 Place a Bet":
            await bet_start(update, context)
            return ConversationHandler.END
        elif text == "📥 Deposit":
            return DEPOSIT_TXN_ID
        elif text == "📤 Withdraw":
            await withdraw_start(update, context)
            return ConversationHandler.END
        elif text in ["💰 Balance", "🕘 History", "🛠 Service"]:
            await start(update, context)
            return ConversationHandler.END

        if not (text.startswith("pay_") and len(text) == 18):
            await update.message.reply_text("❌ Invalid Razorpay Payment ID. It must start with `pay_` and be 18 characters long.")
            return DEPOSIT_TXN_ID

        amount = context.user_data.get("deposit_amount")
        user = update.effective_user

        # Store in DB
        await db.record_deposit(user.id, text, amount)

        # Ensure proper Markdown formatting
        message = (
            f"✅ Deposit request for ₹{amount} with Transaction ID `{text}` has been submitted."
        )

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=main_menu()  # Reintroduce the main menu keyboard
        )
    except Exception as e:
        print(f"Error in receive_transaction_id: {e}")
    return ConversationHandler.END

# -------------------- 📤 WITHDRAW --------------------
# ---- Step 1: Start Withdrawal ----
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()  # Clear previous data
        await update.message.reply_text("💸 How much do you want to withdraw?    Min ₹100", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        print(f"Error in withdraw_start: {e}")
    return WITHDRAW_AMOUNT

# ---- Step 2: Validate amount before asking for UPI ----
async def receive_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()

        # Check if the user selected a new option from the main menu
        if text == "🎯 Place a Bet":
            await bet_start(update, context)
            return ConversationHandler.END
        elif text == "📥 Deposit":
            await deposit_start(update, context)
            return ConversationHandler.END
        elif text == "📤 Withdraw":
            return WITHDRAW_AMOUNT
        elif text in ["💰 Balance", "🕘 History", "🛠 Service"]:
            await start(update, context)
            return ConversationHandler.END

        if not text.isdigit():
            await update.message.reply_text("❗ Please enter a valid number.")
            return WITHDRAW_AMOUNT

        amount = int(text)
        if amount < 100:
            await update.message.reply_text("❌ Minimum withdrawal amount is ₹100. Please enter a higher amount.")
            return WITHDRAW_AMOUNT  # Ask again

        user = update.effective_user
        balance = await db.get_balance(user.id)

        if amount > balance:
            await update.message.reply_text("❌ Insufficient balance. Your current balance is ₹{}.".format(balance))
            return ConversationHandler.END

        context.user_data["withdraw_amount"] = amount
        await update.message.reply_text("💳 Enter your UPI ID for withdrawal:")
    except Exception as e:
        print(f"Error in receive_withdraw_amount: {e}")
    return WITHDRAW_UPI_ID

# ---- Step 3: Take UPI ID and record withdrawal ----
async def receive_withdraw_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()

        # Check if the user selected a new option from the main menu
        if text == "🎯 Place a Bet":
            await bet_start(update, context)
            return ConversationHandler.END
        elif text == "📥 Deposit":
            await deposit_start(update, context)
            return ConversationHandler.END
        elif text == "📤 Withdraw":
            return WITHDRAW_UPI_ID
        elif text in ["💰 Balance", "🕘 History", "🛠 Service"]:
            await start(update, context)
            return ConversationHandler.END

        user = update.effective_user
        amount = context.user_data.get("withdraw_amount")

        await db.record_withdrawal(user.id, text, amount)
        await db.update_balance(user.id, -amount)

        await update.message.reply_text(
            f"✅ Withdrawal request for ₹{amount} to UPI ID {text} submitted.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    except Exception as e:
        print(f"Error in receive_withdraw_upi: {e}")
    return ConversationHandler.END

# -------------------- 🤖 BOT INIT --------------------
async def main():
    try:
        await db.connect()
        print("✅ Connected to the database.")
        print("🤖 Bot is running...")
        
        app = Application.builder().token(TOKEN).build()

        # Commands
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("admin", show_admin_controls))
        app.add_handler(CommandHandler("approve_deposits", show_pending_deposits))
        app.add_handler(CommandHandler("cancel", cancel))

        # Regular Messages
        app.add_handler(MessageHandler(filters.Regex("^Start$"), start))
        app.add_handler(MessageHandler(filters.Text("🔐 Admin"), show_admin_controls))
        app.add_handler(MessageHandler(filters.Text("👥 Users & Balances"), show_all_users))
        app.add_handler(MessageHandler(filters.Text("💰 Balance"), show_balance))
        app.add_handler(MessageHandler(filters.Text("🕘 History"), show_history))
        app.add_handler(MessageHandler(filters.Text("🛠 Service"), show_service))

        # Admin Panel Buttons
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^✅ Approve Deposits$"), show_pending_deposits))
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💸 Approve Withdrawals$"), show_pending_withdrawals))
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^👥 View Users & Balances$"), show_all_users))
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📊 View Admin Profit$"), show_admin_profit))
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🕒 View Recent Bets$"), show_recent_bets))
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔙 Back to Menu$"), start))

        # ✅ Inline Button Handler (for approving deposits/withdrawals)
        app.add_handler(CallbackQueryHandler(handle_approve_callback, pattern="^approve_"))

        admin_result_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("✅ Accept Result"), admin_result.accept_result)],
            states={
                "AWAITING_RESULT_CHOICE": [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, admin_result.handle_result_choice)
                ]
            },
            fallbacks=[],
        )
        
        app.add_handler(admin_result_handler)

        app.add_handler(MessageHandler(filters.Regex("🧮 View Bet Summary"), admin_result.view_bet_summary))

        # Deposit Handler
        deposit_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Text("📥 Deposit"), deposit_start)],
            states={
                DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deposit_amount)],
                DEPOSIT_TXN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_transaction_id)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            per_user=True,
        )
        app.add_handler(deposit_handler)

        # Withdraw Handler
        withdraw_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Text("📤 Withdraw"), withdraw_start)],
            states={
                WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_amount)],
                WITHDRAW_UPI_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_upi)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            per_user=True,
        )
        app.add_handler(withdraw_handler)

        # Betting Handler
        betting_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Text("🎯 Place a Bet"), bet_start)],
            states={
                BET_ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bet_enter_amount)],
                BET_CHOOSE_SIDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bet_choose_side)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            per_user=True,
        )
        app.add_handler(betting_handler)

        app.add_handler(CallbackQueryHandler(handle_approve_callback))

        await app.run_polling()
    except Exception as e:
        print(f"Error in bot initialization: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())


#-----------------------database---------------------
import asyncpg
import os
import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.pool.Pool] = None

    async def connect(self):
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(DATABASE_URL)
                print("[DB] Connected successfully!")
            except Exception as e:
                print(f"[DB ERROR] Failed to connect: {e}")

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    balance INT DEFAULT 0
                );
            ''')

    async def add_user(self, user_id, full_name):
        try:
            # Debugging output
            print(f"Attempting to add user: {user_id}, {full_name}")

            existing = await self.pool.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if existing:
                print(f"User {user_id} already exists in the database.")
                return False  # User already exists

            await self.pool.execute(
                "INSERT INTO users (user_id, full_name, balance) VALUES ($1, $2, 0)",
                user_id, full_name
            )
            print(f"User {user_id} added successfully.")
            return True
        except Exception as e:
            print(f"Error adding user {user_id}: {e}")
            return False

    async def get_balance(self, user_id):
        async with self.pool.acquire() as conn:
            balance = await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
            return balance or 0

    # ───── USER MANAGEMENT ─────

    async def add_user_if_not_exists(self, user_id: int, username: Optional[str] = None):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, balance)
                VALUES ($1, $2, 0)
                ON CONFLICT (user_id) DO NOTHING
            """, user_id, username)

    async def get_current_bets(self):
        query = "SELECT user_id, amount, choice FROM bets"
        return await self.pool.fetch(query)

    async def clear_all_bets(self):
        await self.pool.execute("DELETE FROM bets")

    async def clear_current_bets(self):
        query = "DELETE FROM bets"
        await self.pool.execute(query)

    async def ensure_user(self, user_id: int):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, balance)
                VALUES ($1, 0)
                ON CONFLICT (user_id) DO NOTHING
            """, user_id)

    async def get_balance(self, user_id: int) -> float:
        await self.connect()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
        return float(row["balance"]) if row else 0.0

    async def update_balance(self, user_id: int, amount: float):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)

    async def get_all_users_and_balances(self) -> List[asyncpg.Record]:
        await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT user_id, balance FROM users")

    async def approve_result(self, winning_choice: str):
        bets = await self.pool.fetch(
            "SELECT * FROM bets WHERE timestamp >= NOW() - INTERVAL '30 minutes'"
        )

        winners = []
        losers = []
        total_losing = 0

        for bet in bets:
            if bet["choice"] == winning_choice:
                await self.pool.execute(
                    "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                    bet["amount"] * 2,
                    bet["user_id"]
                )
                winners.append((bet["user_id"], bet["amount"]))
            else:
                total_losing += bet["amount"]
                losers.append((bet["user_id"], bet["amount"]))

        await self.pool.execute(
            "UPDATE admin SET profit = profit + $1 WHERE id = 1",
            total_losing
        )

        await self.pool.execute(
            "DELETE FROM bets WHERE timestamp >= NOW() - INTERVAL '30 minutes'"
        )

        return winners, losers

    async def get_bet_summary(self):
        query = """
            SELECT choice, COUNT(*) AS num_bets, SUM(amount) AS total_amount
            FROM bets
            WHERE timestamp >= NOW() - INTERVAL '30 minutes'
            GROUP BY choice
        """
        rows = await self.pool.fetch(query)

        summary = {"Heads": {"num_bets": 0, "total_amount": 0}, "Tails": {"num_bets": 0, "total_amount": 0}}
        for row in rows:
            summary[row["choice"]] = {
                "num_bets": row["num_bets"],
                "total_amount": row["total_amount"]
            }
        return summary
    async def clear_all_bets(self):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM bets")

    # ───── DEPOSITS & WITHDRAWALS ─────
    async def record_deposit(self, user_id: int, txn_id: str, amount: float):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO deposits (user_id, transaction_id, amount, timestamp, approved)
                VALUES ($1, $2, $3, NOW(), FALSE)
            """, user_id, txn_id, amount)

    async def approve_deposit(self, deposit_id: int):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE deposits SET approved = TRUE WHERE id = $1", deposit_id)
            deposit = await conn.fetchrow("SELECT user_id, amount FROM deposits WHERE id = $1", deposit_id)
            await self.update_balance(deposit["user_id"], deposit["amount"])

    async def apply_approved_deposits(self):
        await self.connect()
        async with self.pool.acquire() as conn:
            deposits = await conn.fetch("""
                SELECT id, user_id, amount
                FROM deposits
                WHERE approved = TRUE AND applied = FALSE
            """)

            for deposit in deposits:
                await conn.execute("""
                    UPDATE users SET balance = balance + $1 WHERE user_id = $2
                """, deposit["amount"], deposit["user_id"])

                await conn.execute("""
                    UPDATE deposits SET applied = TRUE WHERE id = $1
                """, deposit["id"])

            print(f"[✓] Applied {len(deposits)} approved deposit(s) to balances.")

    async def get_pending_deposits(self) -> List[Dict]:
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, amount, transaction_id
                FROM deposits
                WHERE approved = FALSE
            """)
            return [dict(row) for row in rows]

    async def record_withdrawal(self, user_id: int, upi_id: str, amount: float):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO withdrawals (user_id, upi_id, amount, status, requested_at)
                VALUES ($1, $2, $3, 'pending', NOW())
            """, user_id, upi_id, amount)

    async def get_pending_withdrawals(self) -> List[Dict]:
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, amount, upi_id
                FROM withdrawals
                WHERE status = 'pending'
            """)
            return [dict(row) for row in rows]

    # ───── BETTING ─────

    async def record_bet(self, user_id: int, amount: int, choice: str):
        query = "INSERT INTO bets (user_id, amount, choice, timestamp) VALUES ($1, $2, $3, NOW())"
        await self.pool.execute(query, user_id, amount, choice)

    async def update_balance(self, user_id: int, amount: int):
        query = "UPDATE users SET balance = balance + $1 WHERE user_id = $2"
        await self.pool.execute(query, amount, user_id)

    async def add_bet(self, user_id: int, amount: float, choice: str):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bets (user_id, amount, choice)
                VALUES ($1, $2, $3)
            """, user_id, amount, choice)

    async def get_bets_between(self, start_time, end_time, user_id: Optional[int] = None) -> List[asyncpg.Record]:
        await self.connect()
        query = "SELECT * FROM bets WHERE timestamp BETWEEN $1 AND $2"
        params = [start_time, end_time]
        if user_id:
            query += " AND user_id = $3"
            params.append(user_id)
        return await self.pool.fetch(query, *params)

    async def get_previous_bets(self, user_id: int) -> List[asyncpg.Record]:
        await self.connect()
        now = datetime.datetime.now()
        start_of_hour = now.replace(minute=0, second=0, microsecond=0)
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT amount, choice, timestamp
                FROM bets
                WHERE user_id = $1 AND timestamp >= $2
                ORDER BY timestamp DESC
            """, user_id, start_of_hour)

    async def get_recent_bets(self, limit=10) -> List[Dict]:
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, amount, choice, timestamp
                FROM bets
                ORDER BY timestamp DESC
                LIMIT $1
            """, limit)
            return [dict(row) for row in rows]

    async def delete_old_bets(self):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM bets
                WHERE timestamp < date_trunc('hour', now())
            """)

    async def clear_old_bets(self):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM bets")

    # ───── RESULT HANDLING ─────
    async def record_result(self, winners: List[Dict], losers: List[Dict]):
        await self.connect()
        async with self.pool.acquire() as conn:
            for winner in winners:
                await conn.execute("""
                    INSERT INTO bet_results (user_id, result, amount, side)
                    VALUES ($1, 'win', $2, $3)
                """, winner['user_id'], winner['amount'], winner['choice'])
            for loser in losers:
                await conn.execute("""
                    INSERT INTO bet_results (user_id, result, amount, side)
                    VALUES ($1, 'lose', $2, $3)
                """, loser['user_id'], loser['amount'], loser['choice'])

    async def record_draw_result(self, start_time, end_time):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO results (result_time, winning_side, draw, start_time, end_time)
                VALUES (NOW(), NULL, TRUE, $1, $2)
            """, start_time, end_time)

    async def mark_bet_as_draw(self, bet_id: int):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE bets SET is_draw = TRUE WHERE id = $1", bet_id)

    async def calculate_hourly_results(self):
        await self.connect()
        now = datetime.datetime.now()
        start_of_hour = now.replace(minute=0, second=0, microsecond=0)
        end_of_hour = start_of_hour + datetime.timedelta(hours=1)

        async with self.pool.acquire() as conn:
            totals = await conn.fetch("""
                SELECT choice, SUM(amount) AS total
                FROM bets
                WHERE timestamp >= $1 AND timestamp < $2
                GROUP BY choice
            """, start_of_hour, end_of_hour)

            if len(totals) < 2:
                print("[!] Not enough data to calculate result.")
                return

            sorted_totals = sorted(totals, key=lambda x: x["total"])
            winner_choice = sorted_totals[0]["choice"]
            loser_total = sorted_totals[1]["total"]

            winners = await conn.fetch("""
                SELECT user_id, amount FROM bets
                WHERE choice = $1 AND timestamp >= $2 AND timestamp < $3
            """, winner_choice, start_of_hour, end_of_hour)

            for winner in winners:
                payout = winner["amount"] * 2
                await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", payout, winner["user_id"])

            await conn.execute("""
                INSERT INTO admin_profit (hour, profit)
                VALUES ($1, $2)
            """, start_of_hour, loser_total)

            await conn.execute("""
                DELETE FROM bets WHERE timestamp >= $1 AND timestamp < $2
            """, start_of_hour, end_of_hour)

            print(f"[✓] Hourly result: {winner_choice.upper()} wins. Admin earned ₹{loser_total}")

    # ───── TRANSACTIONS & PROFIT ─────
    async def record_transaction(self, user_id: int, tx_type: str, amount: float, description: str = ""):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES ($1, $2, $3, $4)
            """, user_id, tx_type, amount, description)

    async def record_admin_profit(self, amount: float):
        await self.connect()
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO admin_profit (profit) VALUES ($1)", amount)

    async def get_admin_profit(self) -> float:
        await self.connect()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COALESCE(SUM(profit), 0) AS total_profit FROM admin_profit")
            return row["total_profit"]

# Create a shared instance
db = Database()


#----------------------admin_result--------------------

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