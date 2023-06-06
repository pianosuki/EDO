import asyncio
from server import GameServer


async def main():
    server = GameServer(host="127.0.0.1", port=8787, auth_mode=False)
    await asyncio.gather(server.run(), server.simulation_loop(), server.database_sync_task())

if __name__ == "__main__":
    asyncio.run(main())
