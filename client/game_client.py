import asyncio, websockets, aiohttp, os, time
from common.lib import NetworkPacket, GameState, SessionEvent, GameSession, MovementEvent
from .config import *


class GameClient:
    def __init__(self, **kwargs):
        self.host = kwargs.get("host", "127.0.0.1")
        self.port = kwargs.get("port", 8787)
        self.auth_mode = kwargs.get("auth_mode", True)
        self.profile_name = kwargs.get("profile_name", os.getlogin())

        self.mem = None
        self.websocket = None
        self.inbound_queue = asyncio.Queue()
        self.outbound_queue = asyncio.Queue()
        self.auth_event = asyncio.Event()
        self.login_event = asyncio.Event()
        self.credentials = ()
        self.access_token = ""
        self.refresh_token = ""

        self.delta_time = 1 / CLIENT_TICK_HZ  # Time since last simulation loop

    def setup(self, shared_memory):
        self.mem = shared_memory

    async def run(self):
        pull_task = asyncio.create_task(self.pull_task())
        push_task = asyncio.create_task(self.push_task())
        game_handler_task = asyncio.create_task(self.game_handler())
        server_handler_task = asyncio.create_task(self.handle_packet())
        await asyncio.gather(push_task, pull_task, game_handler_task, server_handler_task)

    async def simulation_loop(self):
        while True:
            if not self.login_event.is_set(): await self.login_event.wait()
            start_time = asyncio.get_running_loop().time()

            if self.mem.local_pos != self.mem.old_local_pos:
                event = MovementEvent(0, self.mem.local_pos)
                await asyncio.to_thread(self.mem.queue.put, event)
                self.mem.old_local_pos = self.mem.local_pos

            elapsed_time = asyncio.get_running_loop().time() - start_time
            await asyncio.sleep(max(0, 1 / CLIENT_TICK_HZ - elapsed_time))
            self.delta_time = max(1 / CLIENT_TICK_HZ, elapsed_time)

    async def authenticate(self):
        if self.auth_mode:
            email, password = self.credentials
            print("Initiating authentication process...")
            async with aiohttp.ClientSession() as session:
                headers = {"Content-Type": "application/json"}
                body = {"email": email, "password": password}
                async with session.post(AUTHENTICATION_SERVER + "/api/v1/authenticate", headers=headers, json=body) as response:
                    status_code = response.status
                    response_json = await response.json()
                    match status_code:
                        case 201:
                            print("Authentication was successful!", f"Logged in as '{email}'!")
                            self.access_token, self.refresh_token = (response_json["access_token"], response_json["refresh_token"])
                            self.auth_event.set()
                        case 400:
                            print(status_code, response_json["detail"])
                        case 401:
                            print(status_code, response_json["detail"])
        else:
            print("Skipping authentication process...", f"Logged in as '{self.profile_name}'!")
            self.access_token = self.profile_name
            self.auth_event.set()

    async def connect(self):
        await self.auth_event.wait()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.websocket = await websockets.connect(f"ws://{self.host}:{self.port}", extra_headers=headers)
        print("Connected to Game Server!")

    async def disconnect(self):
        await self.websocket.close()
        print("Disconnected from Game Server!")

    async def send(self, packet: NetworkPacket):
        await self.websocket.send(packet.pack())

    async def recv(self) -> NetworkPacket:
        data = await self.websocket.recv()
        packet = NetworkPacket.unpack(data)
        return packet

    async def pull_task(self):
        while True:
            packet = await self.recv()
            # print(f"Received ({packet.type}) message: {packet.payload}")
            await self.inbound_queue.put(packet)

    async def push_task(self):
        while True:
            packet = await self.outbound_queue.get()
            await self.send(packet)
            # print(f"Sent ({packet.type}) message: {packet.payload}")

    async def game_handler(self):
        while True:
            event = await asyncio.to_thread(self.mem.queue.get)
            match event.__class__.__name__:
                case "SessionEvent":
                    packet = NetworkPacket(NetworkPacket.PacketType.SESSION, event.serialize())
                case "MovementEvent":
                    packet = NetworkPacket(NetworkPacket.PacketType.MOVEMENT, event.serialize())
            await self.outbound_queue.put(packet)

    async def handle_packet(self):
        while True:
            packet = await self.inbound_queue.get()
            match packet.type:
                case NetworkPacket.PacketType.GAMESTATE:
                    game_state = GameState.unserialize(packet.payload)
                    await self.handle_gamestate_event(game_state)
                case NetworkPacket.PacketType.SESSION:
                    event = SessionEvent.unserialize(packet.payload)
                    await self.handle_session_event(event)

    async def handle_gamestate_event(self, game_state: GameState):
        with self.mem.lock:
            now = time.time()
            self.mem.gs = game_state
            self.mem.server_pos = game_state.player_states[self.mem.session.character.get("uuid")].position
            self.mem.gamestate_updated_at = now
            self.mem.average_server_dt = (self.mem.average_server_dt + game_state.delta_time) / 2

    async def handle_session_event(self, event: SessionEvent):
        match event.command:
            case SessionEvent.SessionCommand.SCOPE:
                with self.mem.lock:
                    scope = event.kwargs.get("scope")
                    self.mem.session.scope = scope
            case SessionEvent.SessionCommand.LOGIN:
                with self.mem.lock:
                    character = event.kwargs.get("character")
                    self.mem.session.character = character
                    self.mem.local_pos = character["location"]["x"], character["location"]["y"]
                    self.mem.session.status = GameSession.GameStatus.PLAY
                    self.login_event.set()
            case SessionEvent.SessionCommand.LOGOUT:
                with self.mem.lock:
                    self.mem.session.character.clear()
                    self.mem.session.status = GameSession.GameStatus.IDLE
                    self.login_event.clear()
            case SessionEvent.SessionCommand.CREATE:
                with self.mem.lock:
                    character_uuid = event.kwargs.get("character_uuid")
                    self.mem.session.scope["characters"].append(character_uuid)
            case SessionEvent.SessionCommand.DELETE:
                with self.mem.lock:
                    character_uuid = event.kwargs.get("character_uuid")
                    self.mem.session.scope["characters"].remove(character_uuid)
