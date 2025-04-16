from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.database import get_db_connection

router = Router()

class BetForm(StatesGroup):
    amount = State()
    choice = State()

@router.message(F.text == "🎯 Place a Bet")
async def start_bet(message: Message, state: FSMContext):
    await state.set_state(BetForm.amount)
    await message.answer("💰 Enter your bet amount:")

@router.message(BetForm.amount)
async def receive_bet_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            return await message.answer("🚫 Enter a valid amount.")
        await state.update_data(amount=amount)

        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton("Heads"), KeyboardButton("Tails")]
        ])
        await state.set_state(BetForm.choice)
        await message.answer("🪙 Choose Heads or Tails:", reply_markup=kb)

    except ValueError:
        await message.answer("❌ Please enter a valid number.")

@router.message(BetForm.choice)
async def receive_bet_choice(message: Message, state: FSMContext):
    choice = message.text.strip().lower()
    if choice not in ['heads', 'tails']:
        return await message.answer("❌ Invalid choice. Please choose Heads or Tails.")

    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id

    conn = await get_db_connection()
    try:
        balance = await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
        if not balance or balance < amount:
            return await message.answer("💸 Insufficient balance.")

        await conn.execute("UPDATE users SET balance = balance - $1 WHERE user_id = $2", amount, user_id)
        await conn.execute(
            "INSERT INTO bets (user_id, amount, choice, timestamp) VALUES ($1, $2, $3, NOW())",
            user_id, amount, choice
        )
        await message.answer(
            f"✅ Bet placed: ₹{amount} on {choice.capitalize()}.\nCheck results after 30 mins.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
    finally:
        await conn.close()
