import arcade, asyncio, threading, traceback
import logging
from game import GameWindow
from client import GameClient
from common.lib import SharedMemory

logging.getLogger("arcade").setLevel(logging.WARNING)
shared_memory = SharedMemory()


def thread_worker(client: GameClient):
    asyncio.run(iomain(client))


async def iomain(client):
    try:
        await asyncio.gather(client.authenticate(), client.connect())
        await asyncio.gather(client.run(), client.simulation_loop())
    except Exception as e:
        print(f"ERROR:", type(e).__name__, e)
        traceback.print_exc()
    finally:
        await client.disconnect()


def main():
    window = GameWindow(1280, 720, "game_test")
    window.setup(shared_memory)
    window.show_view(window.menu_view)
    client = GameClient(host="127.0.0.1", port=8787, auth_mode=False, profile_name="Foss")
    client.setup(shared_memory)
    client.credentials = ("email", "password")
    client_thread = threading.Thread(target=thread_worker, args=(client,), daemon=True)
    client_thread.start()
    arcade.run()


if __name__ == "__main__":
    main()
