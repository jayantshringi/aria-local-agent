import aiosqlite
import asyncio
from pathlib import Path

async def set_model():
    db_path = Path("~/.aria/aria.db").expanduser()
    if not db_path.exists():
        print("DB does not exist yet")
        return
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES ('active_chat_model', 'llama3.2:3b') "
            "ON CONFLICT(key) DO UPDATE SET value = 'llama3.2:3b';"
        )
        await db.commit()
        print("Successfully updated settings: active_chat_model -> llama3.2:3b")

if __name__ == "__main__":
    asyncio.run(set_model())
