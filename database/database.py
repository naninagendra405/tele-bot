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

            # Set initial balance to 30 for new users
            await self.pool.execute(
                "INSERT INTO users (user_id, full_name, balance) VALUES ($1, $2, 30)",
                user_id, full_name
            )
            print(f"User {user_id} added successfully with a ₹30 joining bonus.")
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

    async def approve_result(self, winning_choice: str):
        try:
            # Fetch all current bets
            bets = await self.get_current_bets()
            winners = []
            losers = []
            total_losing = 0

            # Calculate winners and losers
            for bet in bets:
                if bet["choice"] == winning_choice:
                    winners.append((bet["user_id"], bet["amount"]))
                    # Update user balance for winners
                    await self.update_balance(bet["user_id"], bet["amount"] * 2)
                else:
                    total_losing += bet["amount"]
                    losers.append((bet["user_id"], bet["amount"]))

            # Update admin profit with the total losing amount
            await self.update_admin_profit(total_losing)

            # Clear bets after settlement
            await self.clear_all_bets()

            return winners, losers
        except Exception as e:
            print(f"Error approving result: {e}")
            return [], []

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

    async def accept_result_and_update_profit(self, winning_choice: str):
        try:
            # Fetch all current bets
            bets = await self.get_current_bets()
            total_losing = 0

            # Calculate total losing amount
            for bet in bets:
                if bet["choice"] != winning_choice:
                    total_losing += bet["amount"]

            # Update admin profit with the total losing amount
            await self.update_admin_profit(total_losing)

            # Clear bets after settlement
            await self.clear_all_bets()

            print(f"Result accepted. Admin profit updated by ₹{total_losing}.")
        except Exception as e:
            print(f"Error accepting result and updating admin profit: {e}")

    async def update_admin_profit(self, losing_amount: float):
        try:
            async with self.pool.acquire() as conn:
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
