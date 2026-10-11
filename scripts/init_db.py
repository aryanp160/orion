import asyncio

from apps.api.database import init_db


async def main():
    print("Initializing ORION SQLite database...")
    await init_db()
    print("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(main())
