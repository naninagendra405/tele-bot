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

        # Register user and check if they are new
        is_new = await db.add_user(user_id, full_name)
        print(f"User registration status: {'New user added' if is_new else 'User already exists'}")

        # Send welcome message if the user is new
        if is_new:
            welcome_message = (
                "Welcome to Twice The Bet! 🎉\n\n"
                "Here are some quick tips to get started:\n"
                "1. **/start Command:** Use `/start` anytime to reset or navigate the bot. 🔄\n"
                "2. **Registration Bonus:** Enjoy a ₹30 bonus just for signing up! 🎁\n"
                "3. **Referral Program:** Invite friends and earn bonuses when they join and deposit. 🤝\n"
                "4. **Responsible Gaming:** Play responsibly. Remember, you can win or lose money. 🎲\n"
                "5. **Need Help?** Reach out to our support team anytime. We're here for you! 📞\n"
                "6. **Stay Updated:** Watch for new features and updates. 🚀\n\n"
                "Thank you for choosing Twice The Bet. Have fun! 🎈"
            )
            await update.message.reply_text(welcome_message, parse_mode="Markdown")

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

async def settle_bets(winning_choice: str):
    try:
        bets = await db.get_current_bets()
        total_losing = 0

        for bet in bets:
            if bet["choice"] != winning_choice:
                total_losing += bet["amount"]

        # Update admin profit with the total losing amount
        await update_admin_profit(total_losing)

        # Clear bets after settlement
        await db.clear_all_bets()
    except Exception as e:
        print(f"Error settling bets: {e}")

async def accept_result_and_update_profit(winning_choice: str):
    try:
        # Fetch all bets
        bets = await db.get_current_bets()
        total_losing = 0

        # Calculate total losing amount
        for bet in bets:
            if bet["choice"] != winning_choice:
                total_losing += bet["amount"]

        # Update admin profit with the total losing amount
        await update_admin_profit(total_losing)

        # Clear bets after settlement
        await db.clear_all_bets()

        print(f"Result accepted. Admin profit updated by ₹{total_losing}.")
    except Exception as e:
        print(f"Error accepting result and updating admin profit: {e}")

async def update_admin_profit(losing_amount: float):
    try:
        async with db.pool.acquire() as conn:
            # Ensure the admin_profit table has an entry to update
            result = await conn.fetchrow("SELECT * FROM admin_profit WHERE id = 1")
            if result is None:
                await conn.execute("INSERT INTO admin_profit (id, profit) VALUES (1, 0)")

            # Update the admin profit by adding the losing amount
            await conn.execute(
                "UPDATE admin_profit SET profit = profit + $1 WHERE id = 1",
                losing_amount
            )
            print(f"Admin profit updated by ₹{losing_amount}.")
    except Exception as e:
        print(f"Error updating admin profit: {e}")

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
