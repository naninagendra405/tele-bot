import asyncio
from database.database import db

async def test_database():
    try:
        # Test connection
        await db.connect()
        
        # Test create tables
        await db.create_tables()
        
        # Test add user
        test_user_id = 123456
        test_name = "Test User"
        success = await db.add_user(test_user_id, test_name)
        print(f"Add user success: {success}")
        
        # Test get balance
        balance = await db.get_balance(test_user_id)
        print(f"User balance: {balance}")
        
        # Test get all users
        users = await db.get_all_users_and_balances()
        print(f"All users: {users}")
        
    except Exception as e:
        print(f"Error in test: {e}")

if __name__ == "__main__":
    asyncio.run(test_database())