import asyncio, websockets, aiohttp, random, string, sqlalchemy.exc, traceback
from http import HTTPStatus
from typing import Optional, Tuple
from common.lib import NetworkPacket, GameState, PlayerState, SessionEvent, MovementEvent, ErrorEvent, ErrorCode, ErrorSeverity, ErrorNature, generate_pseudo_uuid, calculate_distance, calculate_velocity
from .crud import WorldDB
from .config import *


class GameServer:
    def __init__(self, **kwargs):
        self.host = kwargs.get("host", "127.0.0.1")
        self.port = kwargs.get("port", 8787)
        self.auth_mode = kwargs.get("auth_mode", True)

        self.db = WorldDB()
        self.gs = GameState()
        self.clients = set()
        self.users = {}  # Mapping of self.clients to dictionaries of their user data
        self.tasks = {}  # Mapping of self.clients to dictionaries of their tasks
        self.queues = {}  # Mapping of self.clients to dictionaries of their queues
        self.tokens = {}  # Mapping of access tokens to User UUIDs from the Authentication Server
        self.players = {}  # Mapping of self.clients to PlayerState objects in the GameState
        self.characters = {}  # Mapping of self.clients to Character UUIDs they are logged in as

        self.delta_time = 1 / SERVER_TICK_HZ  # Time since last simulation loop

    async def run(self):
        async with websockets.serve(self.handle_connection, self.host, self.port, process_request=self.process_request):
            print(f"[{self.__class__.__name__}] Recreating the database...")
            await self.db.recreate_database()
            await self.db.populate_database()
            print(f"[{self.__class__.__name__}] Started the server!")
            await asyncio.Future()

    async def simulation_loop(self):
        while True:
            start_time = asyncio.get_running_loop().time()

            for player in self.gs.player_states.values():
                player.updated_at = start_time

            elapsed_time = asyncio.get_running_loop().time() - start_time
            await asyncio.sleep(max(0, 1 / SERVER_TICK_HZ - elapsed_time))
            self.delta_time = max(1 / SERVER_TICK_HZ, elapsed_time)

    async def database_sync_task(self):
        while True:
            for character_uuid, player in self.gs.player_states.items():
                await self.database_sync_player(character_uuid, player)
            await asyncio.sleep(1 / DATABASE_SYNC_HZ)

    async def database_sync_player(self, character_uuid: str, player: PlayerState):
        await self.db.update_chracter_by_uuid(character_uuid, player.to_dict())

    async def process_request(self, path: str, request_headers: websockets.Headers) -> Optional[Tuple[HTTPStatus, websockets.datastructures.HeadersLike, bytes]]:
        try:
            access_token = request_headers["Authorization"].split()[1]
            is_authenticated = await self.authenticate(access_token)
        except (KeyError, IndexError):
            response_headers = {"WWW-Authenticate": "Bearer"}
            return HTTPStatus.UNAUTHORIZED, response_headers, b"Unauthorized"

        if is_authenticated:
            return None
        else:
            response_headers = {"WWW-Authenticate": f'Bearer error="{access_token}"'}
            return HTTPStatus.UNAUTHORIZED, response_headers, b"Unauthorized"

    async def authenticate(self, access_token: str) -> bool:
        if self.auth_mode:
            async with aiohttp.ClientSession() as session:
                params = {"access_token": access_token}
                async with session.get(AUTHENTICATION_SERVER + "/api/v1/authenticate", params=params) as response:
                    response_json = await response.json()
                    match response.status:
                        case 200:
                            self.tokens[access_token] = response_json["uuid"]
                            return True
                        case 401:
                            return False
        else:
            self.tokens[access_token] = generate_pseudo_uuid(access_token)
            return True

    async def handle_connection(self, client: websockets.WebSocketServerProtocol, path: str):
        try:
            print(f"[{self.__class__.__name__}] Adding client: {client}")
            self.clients.add(client)
            self.users[client] = {}
            self.tasks[client] = {}
            self.queues[client] = {}
            await self.handle_client(client)
        except websockets.exceptions.ConnectionClosedError:
            pass
        except Exception as e:
            print(f"[{self.__class__.__name__}] ERROR:", type(e).__name__, e)
            traceback.print_exc()
        finally:
            print(f"[{self.__class__.__name__}] Removing client: {client}")
            await self.handle_disconnection(client)
            self.clients.remove(client)
            for task in self.tasks[client].values(): task.cancel()
            del self.users[client]
            del self.tasks[client]
            del self.queues[client]

    async def handle_disconnection(self, client: websockets.WebSocketServerProtocol):
        if client in self.players: await self.despawn_player(client)

    async def handle_client(self, client: websockets.WebSocketServerProtocol):
        await self.init_user(client)
        self.queues[client]["inbound_queue"] = asyncio.Queue()
        self.queues[client]["outbound_queue"] = asyncio.Queue()
        self.queues[client]["movement_queue"] = asyncio.Queue()
        self.tasks[client]["pull_task"] = asyncio.create_task(self.pull_task(client))
        self.tasks[client]["push_task"] = asyncio.create_task(self.push_task(client))
        self.tasks[client]["handler_task"] = asyncio.create_task(self.handle_packet(client))
        await asyncio.gather(self.tasks[client]["pull_task"], self.tasks[client]["push_task"], self.tasks[client]["handler_task"])

    async def init_user(self, client: websockets.WebSocketServerProtocol):
        access_token = client.request_headers["Authorization"].split()[1]
        user_uuid = self.tokens[access_token]
        try:
            user_id = await self.db.get_user_id_by_uuid(user_uuid)
        except sqlalchemy.exc.NoResultFound:
            await self.db.create_user(user_uuid)
            user_id = await self.db.get_user_id_by_uuid(user_uuid)
        finally:
            await self.db.create_character(user_id, {"name": "".join(random.choices(string.ascii_letters, k=8))}, {})
            character_uuids = await self.db.get_user_character_uuids(user_id)
            self.users[client]["id"] = user_id
            self.users[client]["uuid"] = user_uuid
            self.users[client]["characters"] = {uuid for uuid in character_uuids}

    async def send(self, client: websockets.WebSocketServerProtocol, packet: NetworkPacket):
        await client.send(packet.pack())

    async def recv(self, client: websockets.WebSocketServerProtocol) -> NetworkPacket:
        data = await client.recv()
        packet = NetworkPacket.unpack(data)
        return packet

    async def pull_task(self, client: websockets.WebSocketServerProtocol):
        """ PULL TASK """
        while True:
            packet = await self.recv(client)
            # print(f"[{self.__class__.__name__}] Received ({packet.type}) message: {packet.payload}")
            await self.queues[client]["inbound_queue"].put(packet)

    async def push_task(self, client: websockets.WebSocketServerProtocol):
        """ PUSH TASK """
        while True:
            packet = await self.queues[client]["outbound_queue"].get()
            await self.send(client, packet)
            # print(f"[{self.__class__.__name__}] Sent ({packet.type}) message: {packet.payload}")

    async def handle_packet(self, client: websockets.WebSocketServerProtocol):
        outbound_queue = self.queues[client]["outbound_queue"]
        while True:
            packet = await self.queues[client]["inbound_queue"].get()
            match packet.type:
                case NetworkPacket.PacketType.SESSION:
                    event = SessionEvent.deserialize(packet.payload)
                    await self.handle_session_event(client, event)
                case NetworkPacket.PacketType.MOVEMENT:
                    event = MovementEvent.deserialize(packet.payload)
                    await self.handle_movement_event(client, event)

    async def handle_session_event(self, client: websockets.WebSocketServerProtocol, event: SessionEvent):
        match event.command:
            case SessionEvent.SessionCommand.SCOPE:
                scope = {
                    "characters": [character for character in self.users[client]["characters"]]
                }
                event = SessionEvent(SessionEvent.SessionCommand.SCOPE, scope=scope)
                packet = NetworkPacket(NetworkPacket.PacketType.SESSION, event.serialize())
                await self.queues[client]["outbound_queue"].put(packet)
            case SessionEvent.SessionCommand.LOGIN:
                character_uuid = event.kwargs.get("character_uuid")
                if character_uuid is None:
                    error = ErrorEvent(ErrorCode.INVALID_REQUEST, ErrorSeverity.LOW, ErrorNature.BENIGN, "Missing keyword argument: \"{}\"".format("character_uuid"), "{}".format(event))
                elif character_uuid not in self.users[client]["characters"] and False:  # Remove False later
                    error = ErrorEvent(ErrorCode.AUTHORIZATION_ERROR, ErrorSeverity.LOW, ErrorNature.BENIGN, "Unauthorized use of keyword argument: \"{}\"".format("character_uuid"), "{}".format(event))
                elif client in self.players:
                    error = ErrorEvent(ErrorCode.CONFLICT, ErrorSeverity.LOW, ErrorNature.BENIGN, "Currently logged in", "{}".format(event))
                else:
                    character = await self.db.get_character_by_uuid(character_uuid)
                    event = SessionEvent(SessionEvent.SessionCommand.LOGIN, character=character.to_dict())
                    packet = NetworkPacket(NetworkPacket.PacketType.SESSION, event.serialize())
                    await self.queues[client]["outbound_queue"].put(packet)
                    await self.spawn_player(client, character_uuid)
                    self.tasks[client]["publish_game_state"] = asyncio.create_task(self.publish_game_state(client))
            case SessionEvent.SessionCommand.LOGOUT:
                if client not in self.players:
                    error = ErrorEvent(ErrorCode.CONFLICT, ErrorSeverity.LOW, ErrorNature.BENIGN, "Currently logged out", "{}".format(event))
                else:
                    await self.despawn_player(client)
                    self.tasks[client]["publish_game_state"].cancel()
                    del self.tasks[client]["publish_game_state"]
                    event = SessionEvent(SessionEvent.SessionCommand.LOGOUT)
                    packet = NetworkPacket(NetworkPacket.PacketType.SESSION, event.serialize())
                    await self.queues[client]["outbound_queue"].put(packet)
            case SessionEvent.SessionCommand.CREATE:
                character_attributes = event.kwargs.get("character_attributes")
                character_properties = event.kwargs.get("character_properties")
                if character_attributes is None:
                    error = ErrorEvent(ErrorCode.INVALID_REQUEST, ErrorSeverity.LOW, ErrorNature.BENIGN, "Missing keyword argument: \"{}\"".format("character_attributes"), "{}".format(event))
                elif character_properties is None:
                    error = ErrorEvent(ErrorCode.INVALID_REQUEST, ErrorSeverity.LOW, ErrorNature.BENIGN, "Missing keyword argument: \"{}\"".format("character_properties"), "{}".format(event))
                elif await self.db.check_user_has_max_characters(self.users[client]["id"]):
                    error = ErrorEvent(ErrorCode.OUT_OF_BOUNDS, ErrorSeverity.LOW, ErrorNature.BENIGN, "Character limit reached", "{}".format(event))
                elif await self.db.check_character_name_exists(character_attributes["name"]):
                    error = ErrorEvent(ErrorCode.RESERVED, ErrorSeverity.LOW, ErrorNature.BENIGN, "Character name already taken", "{}".format(event))
                elif client in self.players:
                    error = ErrorEvent(ErrorCode.CONFLICT, ErrorSeverity.LOW, ErrorNature.BENIGN, "Currently logged in", "{}".format(event))
                else:
                    print("CREATING CHARACTER")
                    await self.db.create_character(self.users[client]["id"], character_attributes, character_properties)
                    character_uuid = await self.db.get_character_uuid_by_name(character_attributes["name"])
                    self.users[client]["characters"].add(character_uuid)
                    event = SessionEvent(SessionEvent.SessionCommand.CREATE, character_uuid=character_uuid)
                    packet = NetworkPacket(NetworkPacket.PacketType.SESSION, event.serialize())
                    await self.queues[client]["outbound_queue"].put(packet)
            case SessionEvent.SessionCommand.DELETE:
                character_uuid = event.kwargs.get("character_uuid")
                if character_uuid is None:
                    error = ErrorEvent(ErrorCode.INVALID_REQUEST, ErrorSeverity.LOW, ErrorNature.BENIGN, "Missing keyword argument: \"{}\"".format("character_uuid"), "{}".format(event))
                elif character_uuid not in self.users[client]["characters"] and False: # Remove False later
                    error = ErrorEvent(ErrorCode.AUTHORIZATION_ERROR, ErrorSeverity.LOW, ErrorNature.BENIGN, "Unauthorized use of keyword argument: \"{}\"".format("character_uuid"), "{}".format(event))
                elif client in self.players:
                    error = ErrorEvent(ErrorCode.CONFLICT, ErrorSeverity.LOW, ErrorNature.BENIGN, "Currently logged in", "{}".format(event))
                else:
                    print("DELETING CHARACTER")
                    await self.db.delete_character_by_uuid(character_uuid)
                    self.users[client]["characters"].remove(character_uuid)
                    event = SessionEvent(SessionEvent.SessionCommand.DELETE, character_uuid=character_uuid)
                    packet = NetworkPacket(NetworkPacket.PacketType.SESSION, event.serialize())
                    await self.queues[client]["outbound_queue"].put(packet)

    async def handle_movement_event(self, client: websockets.WebSocketServerProtocol, event: MovementEvent):
        self.players[client].velocity = calculate_velocity(event.keys)
        old_pos = self.players[client].position
        new_pos = event.position
        distance = calculate_distance(old_pos, new_pos)
        print(old_pos, new_pos, distance)
        self.players[client].position = new_pos

    async def publish_game_state(self, client: websockets.WebSocketServerProtocol):
        while True:
            game_state = self.filter_game_state(client)
            packet = NetworkPacket(NetworkPacket.PacketType.GAMESTATE, game_state.serialize())
            await self.queues[client]["outbound_queue"].put(packet)
            await asyncio.sleep(1 / SERVER_TICK_HZ)

    def filter_game_state(self, client: websockets.WebSocketServerProtocol) -> GameState:
        player_states = {character_uuid: player for character_uuid, player in self.gs.player_states.items() if player.map_id == self.players[client].map_id}
        return GameState(player_states=player_states, delta_time=self.delta_time)

    async def spawn_player(self, client: websockets.WebSocketServerProtocol, character_uuid: str):
        character = await self.db.get_character_by_uuid(character_uuid)
        player_state = PlayerState(map_id=character.map_id, x=character.x, y=character.y, travel_speed=200)
        self.gs.player_states[character_uuid] = player_state
        self.players[client] = player_state
        self.characters[client] = character_uuid

        self.players[client].position = (character.x, character.y)

    async def despawn_player(self, client: websockets.WebSocketServerProtocol):
        character_uuid = self.characters[client]
        await self.database_sync_player(character_uuid, self.gs.player_states[character_uuid])
        del self.gs.player_states[character_uuid]
        del self.players[client]
        del self.characters[client]
