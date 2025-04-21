import asyncpg
import os
import datetime
from typing import Optional, List, Dict


DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        try:
            if not self.pool:
                self.pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,
                    command_timeout=60
                )
                print("✅ Connected to database successfully!")
        except Exception as e:
            print(f"❌ Database connection error: {e}")

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    balance INT DEFAULT 0
                );
            ''')

    async def add_user(self, user_id: int, full_name: str, referrer_id: Optional[int] = None):
        try:
            print(f"Attempting to add user: {user_id}, {full_name}, referred by: {referrer_id}")

            existing = await self.pool.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if existing:
                print(f"User {user_id} already exists in the database.")
                return False  # User already exists

            # Set initial balance to 30 for new users
            await self.pool.execute(
                "INSERT INTO users (user_id, full_name, balance, referrer_id) VALUES ($1, $2, 30, $3)",
                user_id, full_name, referrer_id
            )
            print(f"User {user_id} added successfully with a ₹30 joining bonus.")
            return True
        except Exception as e:
            print(f"Error adding user {user_id}: {e}")
            return False

    async def get_user_full_name(self, user_id: int) -> Optional[str]:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT full_name FROM users WHERE user_id = $1", user_id)
                return row["full_name"] if row else None
        except Exception as e:
            print(f"Error fetching full name for user {user_id}: {e}")
            return None
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

    async def get_main_balance(self, user_id: int) -> float:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT balance FROM users WHERE user_id = $1",
                    user_id
                )
                return float(row['balance']) if row else 0.0
        except Exception as e:
            print(f"Error getting main balance for user {user_id}: {e}")
            return 0.0
        
    async def get_total_wagered(self, user_id: int) -> float:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(amount), 0) as total_wagered 
                    FROM bets 
                    WHERE user_id = $1
                """, user_id)
                return float(row['total_wagered'])
        except Exception as e:
            print(f"Error getting total wagered amount for user {user_id}: {e}")
            return 0.0
    async def get_all_user_ids(self) -> List[int]:
        await self.connect()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [row['user_id'] for row in rows]

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

    async def award_referral_bonus(self, referrer_id: int):
        try:
            bonus = 10  # Fixed bonus of ₹10
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET balance = balance + $1, referral_bonus = referral_bonus + $1, referral_count = referral_count + 1 WHERE user_id = $2", 
                    bonus, referrer_id
                )
                print(f"Referral bonus of ₹{bonus} awarded to user {referrer_id}")
        except Exception as e:
            print(f"Error awarding referral bonus to user {referrer_id}: {e}")

    # ───── DEPOSITS & WITHDRAWALS ─────
    async def record_deposit(self, user_id: int, txn_id: str, amount: float) -> bool:
        try:
            async with self.pool.acquire() as conn:
                # Extensive validation
                if not user_id or not txn_id:
                    print("❌ Invalid user ID or transaction ID")
                    return False

                # Validate amount
                if amount <= 0:
                    print(f"❌ Invalid deposit amount: {amount}")
                    return False

                # Check for duplicate transaction
                existing = await conn.fetchrow(
                    "SELECT * FROM deposits WHERE transaction_id = $1", 
                    txn_id
                )
                if existing:
                    print(f"❌ Deposit with transaction ID {txn_id} already exists")
                    return False

                # Record deposit
                await conn.execute("""
                    INSERT INTO deposits (
                        user_id, 
                        transaction_id, 
                        amount, 
                        timestamp, 
                        approved,
                        applied
                    ) VALUES ($1, $2, $3, NOW(), FALSE, FALSE)
                """, user_id, txn_id, amount)
                
                print(f"✅ Deposit recorded for user {user_id}: ₹{amount}")

                # Check if this is the first approved deposit
                first_deposit = await conn.fetchval(
                    "SELECT COUNT(*) = 0 FROM deposits WHERE user_id = $1 AND approved = TRUE", 
                    user_id
                )

                # Handle referral bonus
                if first_deposit and amount >= 100:
                    referrer_id = await conn.fetchval(
                        "SELECT referrer_id FROM users WHERE user_id = $1", 
                        user_id
                    )
                    if referrer_id:
                        bonus = 10  # Fixed bonus of ₹10
                        await conn.execute(
                            "UPDATE users SET balance = balance + $1 WHERE user_id = $2", 
                            bonus, referrer_id
                        )
                        print(f"Referral bonus of ₹{bonus} awarded to user {referrer_id}")

                return True
        except Exception as e:
            print(f"❌ Error recording deposit: {e}")
            return False
    async def mark_welcome_as_shown(self, user_id: int):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("UPDATE users SET welcome_shown = TRUE WHERE user_id = $1", user_id)
                print(f"Welcome message marked as shown for user {user_id}.")
        except Exception as e:
            print(f"Error marking welcome as shown for user {user_id}: {e}")

    async def get_pending_deposits(self) -> List[Dict]:
        try:
            await self.connect()
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT 
                        id, 
                        user_id, 
                        amount, 
                        transaction_id,
                        timestamp
                    FROM deposits
                    WHERE approved = FALSE
                    ORDER BY timestamp DESC
                    """
                )
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ Error fetching pending deposits: {e}")
            return []

    async def has_welcome_been_shown(self, user_id: int) -> bool:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT welcome_shown FROM users WHERE user_id = $1", user_id)
                return row["welcome_shown"] if row else False
        except Exception as e:
            print(f"Error checking welcome status for user {user_id}: {e}")
            return False

    async def approve_deposit(self, deposit_id: int) -> bool:
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    deposit = await conn.fetchrow(
                        "SELECT * FROM deposits WHERE id = $1 AND approved = FALSE FOR UPDATE", 
                        deposit_id
                    )
                    if not deposit:
                        print(f"Deposit {deposit_id} not found or already approved")
                        return False

                    await conn.execute(
                        "UPDATE deposits SET approved = TRUE WHERE id = $1", 
                        deposit_id
                    )
                    await conn.execute(
                        "UPDATE users SET balance = balance + $1 WHERE user_id = $2", 
                        deposit["amount"], 
                        deposit["user_id"]
                    )
                    print(f"Deposit {deposit_id} approved successfully")
                    return True
        except Exception as e:
            print(f"Detailed error approving deposit {deposit_id}: {e}")
            return False
    async def approve_withdrawal(self, withdrawal_id: int) -> (bool, Optional[dict]):
        try:
            await self.connect()
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    withdrawal = await conn.fetchrow(
                        "SELECT * FROM withdrawals WHERE id = $1 AND status = 'pending' FOR UPDATE", 
                        withdrawal_id
                    )
                    if not withdrawal:
                        return False, None

                    await conn.execute(
                        "UPDATE withdrawals SET status = 'approved' WHERE id = $1", 
                        withdrawal_id
                    )
                    return True, withdrawal
        except Exception as e:
            print(f"Detailed error approving withdrawal {withdrawal_id}: {e}")
            return False, None

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

    # Database function to approve deposit by transaction ID
    async def approve_deposit_by_transaction_id(self, transaction_id: str) -> bool:
        try:
            await self.connect()
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    deposit = await conn.fetchrow(
                        "SELECT * FROM deposits WHERE transaction_id = $1 AND approved = FALSE FOR UPDATE", 
                        transaction_id
                    )
                    if not deposit:
                        return False

                    await conn.execute(
                        "UPDATE deposits SET approved = TRUE WHERE transaction_id = $1", 
                        transaction_id
                    )
                    await conn.execute(
                        "UPDATE users SET balance = balance + $1 WHERE user_id = $2", 
                        deposit["amount"], 
                        deposit["user_id"]
                    )
                    return True, deposit
        except Exception as e:
            return False
    async def record_withdrawal(self, user_id: int, upi_id: str, amount: float):
        try:
            await self.connect()
            async with self.pool.acquire() as conn:
                # Check user balance before withdrawal
                user_balance = await conn.fetchval(
                    "SELECT balance FROM users WHERE user_id = $1", 
                    user_id
                )
                
                if user_balance < amount:
                    print(f"Insufficient balance for user {user_id}")
                    return False

                await conn.execute("""
                    INSERT INTO withdrawals (user_id, upi_id, amount, status, requested_at)
                    VALUES ($1, $2, $3, 'pending', NOW())
                """, user_id, upi_id, amount)
            return True
        except Exception as e:
            print(f"Error recording withdrawal: {e}")
            return False

    async def get_pending_withdrawals(self) -> List[Dict]:
        try:
            await self.connect()
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT 
                        id, 
                        user_id, 
                        amount, 
                        upi_id
                    FROM withdrawals
                    WHERE status = 'pending'
                    ORDER BY requested_at DESC
                    """
                )
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error fetching pending withdrawals: {e}")
            return []

    # ───── BETTING ─────

    async def record_bet(self, user_id: int, amount: float, choice: str):
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # First check if user has sufficient balance
                    current_balance = await conn.fetchval(
                        "SELECT balance FROM users WHERE user_id = $1",
                        user_id
                    )
                    
                    if current_balance < amount:
                        return False, "Insufficient balance"

                    # Record the bet and deduct balance in a single transaction
                    await conn.execute("""
                        INSERT INTO bets (user_id, amount, choice, timestamp)
                        VALUES ($1, $2, $3, NOW())
                    """, user_id, amount, choice)

                    # Deduct the bet amount from the user's balance
                    await conn.execute("""
                        UPDATE users
                        SET balance = balance - $1
                        WHERE user_id = $2
                    """, amount, user_id)

                    return True, "Bet placed successfully"
        except Exception as e:
            print(f"Error recording bet for user {user_id}: {e}")
            return False, f"Error: {str(e)}"

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
