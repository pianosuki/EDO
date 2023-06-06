import time, json, struct, uuid, hashlib, threading, queue, math
from enum import Enum
from typing import Iterable, Tuple
from collections import deque
from arcade import key as keycodes
from pymunk import Vec2d

CLIENT_TICK_HZ = 5
SERVER_TICK_HZ = 5


def generate_uuid() -> str:
    return uuid.uuid4().hex


def generate_pseudo_uuid(input_string: str) -> str:
    hashed_string = hashlib.sha256(input_string.encode('utf-8')).hexdigest()
    return uuid.UUID(hashed_string[:32]).hex


def map_bitfield(source: Iterable, mapping: Iterable) -> int:
    bitfield = 0
    bitmask = (1 << len(mapping)) - 1
    for bit_index, item in enumerate(mapping):
        if item in source:
            bitfield |= 1 << bit_index
    return bitfield & bitmask


def unmap_bitfield(source: int, mapping: Iterable) -> Iterable:
    result = []
    for bit_index, item in enumerate(mapping):
        if source & (1 << bit_index):
            result.append(item)
    return result


def calculate_distance(pos1: Tuple[float, float], pos2: Tuple[float, float]):
    return math.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)


def calculate_velocity(movement_keys: int) -> Tuple[float, float]:
    SPRINT_MULTIPLIER = 2.0
    velocity = Vec2d(0, 0)

    if movement_keys & MovementKey.LEFT.value:
        velocity += Vec2d(-1, 0)
    if movement_keys & MovementKey.UP.value:
        velocity += Vec2d(0, 1)
    if movement_keys & MovementKey.RIGHT.value:
        velocity += Vec2d(1, 0)
    if movement_keys & MovementKey.DOWN.value:
        velocity += Vec2d(0, -1)

    if velocity.length > 0:
        velocity = velocity.normalized()

    if movement_keys & MovementKey.CTRL.value:
        velocity *= SPRINT_MULTIPLIER

    return velocity.x, velocity.y


def simulate_movement(player_pos: Tuple[float, float], player_vel: Tuple[float, float], player_spd: int, dt: float) -> Tuple[float, float]:
    player_pos = Vec2d(player_pos[0], player_pos[1])
    player_vel = Vec2d(player_vel[0], player_vel[1])

    if player_vel.length > 0:
        player_pos += player_vel * player_spd * dt

    return player_pos.x, player_pos.y


class SharedMemory:
    def __init__(self):
        self.lock = threading.Lock()
        self.queue = queue.Queue()
        self.loopback_queue = queue.Queue()
        self.session = GameSession()
        self.gs = GameState()
        self.gamestate_updated_at = None
        self.average_server_dt = 1 / SERVER_TICK_HZ
        self.old_local_pos = (0, 0)
        self.local_pos = (0, 0)
        self.local_velocity = (0, 0)
        self.server_pos = (0, 0)


class GameSession:

    class GameStatus(Enum):
        IDLE = 0
        PLAY = 1

    def __init__(self):
        self.status = self.GameStatus.IDLE
        self.character = {}  # Dictionary of the Character model
        self.scope = {}  # Scope of permissions, characters, etc. that the user has access to


class PlayerInput:

    MOVEMENT_KEYS = (keycodes.LEFT, keycodes.UP, keycodes.RIGHT, keycodes.DOWN, keycodes.LSHIFT, keycodes.LCTRL, keycodes.SPACE)
    BUFFER_DELAY = 0.1

    def __init__(self, **kwargs):
        self.keys = kwargs.get("keys", set())  # Set of all keys currently pressed
        self.modifiers = kwargs.get("modifiers", 0)  # Bit-wise representation of all modifier keys currently pressed
        self.buffer = deque()  # Keeps track of the keystroke history whithin BUFFER_DELAY seconds to allow grouping
        self.lock = threading.Lock()  # Synchronizes reading and writing attempts to self.keys

    def handle_key_press(self, symbol: int, modifiers: int):
        self.buffer.append((symbol, True))
        self.modifiers = modifiers

    def handle_key_release(self, symbol: int, modifiers: int):
        self.buffer.append((symbol, False))
        self.modifiers = modifiers

    def add_keys(self, symbols: Iterable):
        self.keys.update(symbols)

    def remove_keys(self, symbols: Iterable):
        try:
            self.keys.difference_update(symbols)
        except KeyError:
            # Handle a bug with certain systems' keyboard mappings which cause certain keys to act as other keys while certain keys are held.
            # This can cause issues with trying to remove keys that were never pressed depending on the player's keystroke orders.
            # E.g. (on some Unix systems): SHIFT + ALT turns ALT into META whereas ALT + SHIFT behaves fine.
            # Safest way to prevent those keys from sticking is to just clear the set in the case of such an issue.
            self.keys.clear()

    def to_bitfield(self) -> int:
        return map_bitfield(self.keys, self.MOVEMENT_KEYS)

    @classmethod
    def from_bitfield(cls, movement_data: int):
        keys = unmap_bitfield(movement_data, cls.MOVEMENT_KEYS)
        return cls(keys=keys)


class NetworkPacket:

    class PacketType(Enum):
        META = 0  # MetaInfo()
        GAMESTATE = 1  # GameState()
        ERROR = 2  # ErrorEvent()
        SESSION = 3  # SessionEvent()
        MOVEMENT = 4  # MovementEvent()
        CHAT = 5  # ChatEvent()
        UNKNOWN = 255

    HEADER_FORMAT = "!BI"

    def __init__(self, packet_type: PacketType, data: str):
        self.type = packet_type
        self.payload = data

    def pack(self) -> bytes:
        data = self.encode(self.payload)
        header = struct.pack(self.HEADER_FORMAT, self.type.value, len(data))
        packet = header + data
        return packet

    @classmethod
    def unpack(cls, data: bytes):
        header_size = struct.calcsize(cls.HEADER_FORMAT)
        header = data[:header_size]
        packet_type, data_size = struct.unpack(cls.HEADER_FORMAT, header)
        payload = cls.decode(data[header_size:header_size + data_size])
        return cls(cls.PacketType(packet_type), payload)

    @staticmethod
    def encode(data: str) -> bytes:
        return data.encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> str:
        return data.decode("utf-8")


class SessionEvent:

    class SessionCommand(Enum):
        SCOPE = 0
        LOGIN = 1
        LOGOUT = 2
        CREATE = 3
        DELETE = 4

    def __init__(self, session_command: SessionCommand, **session_kwargs):
        self.command = session_command
        self.kwargs = session_kwargs
        print(__class__, self.command, self.kwargs)

    def __repr__(self):
        return "SessionEvent({}, {})".format(self.command, self.kwargs)

    def serialize(self) -> str:
        session = json.dumps({**self.kwargs, **{"command": self.command.value}})
        return session

    @classmethod
    def unserialize(cls, event: str):
        session_kwargs = json.loads(event)
        session_command = cls.SessionCommand(session_kwargs.pop("command"))
        return cls(session_command, **session_kwargs)


class MovementKey(Enum):
    LEFT = 0b00000001, keycodes.LEFT
    UP = 0b00000010, keycodes.UP
    RIGHT = 0b00000100, keycodes.RIGHT
    DOWN = 0b00001000, keycodes.DOWN
    SHIFT = 0b00010000, keycodes.LSHIFT
    CTRL = 0b00100000, keycodes.LCTRL
    SPACE = 0b01000000, keycodes.SPACE

    def __init__(self, value, keycode):
        self._value_ = value
        self.keycode = keycode

    @classmethod
    def from_value(cls, value):
        match value:
            case 1:
                return cls.LEFT
            case 2:
                return cls.UP
            case 4:
                return cls.RIGHT
            case 8:
                return cls.DOWN
            case 16:
                return cls.SHIFT
            case 32:
                return cls.CTRL
            case 64:
                return cls.SPACE
            case _:
                return None

    @classmethod
    def from_keycode(cls, keycode):
        match keycode:
            case keycodes.LEFT:
                return cls.LEFT
            case keycodes.UP:
                return cls.UP
            case keycodes.RIGHT:
                return cls.RIGHT
            case keycodes.DOWN:
                return cls.DOWN
            case keycodes.LSHIFT:
                return cls.SHIFT
            case keycodes.LCTRL:
                return cls.CTRL
            case keycodes.SPACE:
                return cls.SPACE
            case _:
                return None


class MovementEvent:
    def __init__(self, movement_keys: int, position: Tuple[float, float]):
        self.keys = movement_keys
        self.position = position

    def serialize(self) -> str:
        return json.dumps({
            "keys": self.keys,
            "position": self.position
        })

    @classmethod
    def unserialize(cls, event: str):
        event = json.loads(event)
        return cls(event["keys"], event["position"])


class ChatChannel(Enum):
    GLOBAL = 0
    LOCAL = 1
    GROUP = 2
    PARTY = 3
    WHISPER = 4


class ChatEvent:
    pass


class GameState:
    def __init__(self, **kwargs):
        self.player_states = kwargs.get("player_states", {}) # Dictionary of Character UUIDs to PlayerState instances
        self.delta_time = kwargs.get("delta_time", 1 / SERVER_TICK_HZ) # Time since last game state

    def to_dict(self) -> dict:
        return {
            "player_states": {k: v.serialize() for k, v in self.player_states.items()},
            "delta_time": self.delta_time
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def unserialize(cls, game_state: str):
        kwargs = json.loads(game_state)
        kwargs["player_states"] = {k: PlayerState.unserialize(v) for k, v in kwargs["player_states"].items()}
        return cls(**kwargs)


class PlayerState:
    def __init__(self, **kwargs):
        self.map_id = kwargs.get("map_id", 0)
        self.position = kwargs.get("position", (0, 0))
        self.z_index = kwargs.get("z_index", 1)
        self.travel_speed = kwargs.get("travel_speed", 200)
        self.updated_at = kwargs.get("updated_at", time.time())

    def to_dict(self) -> dict:
        return {
            "map_id": self.map_id,
            "position": self.position,
            "travel_speed": self.travel_speed,
            "updated_at": self.updated_at
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def unserialize(cls, player_state: str):
        kwargs = json.loads(player_state)
        for k, v in kwargs.items():
            kwargs[k] = v
        return cls(**kwargs)


class ActorSprite(Enum):
    RED_CIRCLE = 0


class GameActor:
    def __init__(self, sprite: ActorSprite, position: Tuple[float, float]):
        self.sprite = sprite
        self.x = position[0]
        self.y = position[1]


class ErrorCode(Enum):
    NETWORK_ERROR = 0
    INVALID_REQUEST = 1
    AUTHENTICATION_ERROR = 2
    AUTHORIZATION_ERROR = 3
    SERVER_ERROR = 4
    OUT_OF_BOUNDS = 5
    RESERVED = 6
    CONFLICT = 7
    UNKNOWN = 255


class ErrorSeverity(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3
    UNKNOWN = 255


class ErrorNature(Enum):
    BENIGN = 0
    COSMETIC = 1
    GAMEPLAY = 2
    RUNTIME = 3
    ABUSE = 4
    UNKNOWN = 255


class ErrorEvent:
    def __init__(self, error_code: ErrorCode, error_severity: ErrorSeverity, error_nature: ErrorNature, error_message: str, failed_action: str):
        self.code = error_code
        self.severity = error_severity
        self.nature = error_nature
        self.message = error_message
        self.action = failed_action
        print(__class__, self.code, self.severity, self.nature, self.message, self.action)

    def serialize(self) -> str:
        return json.dumps({
            "error_code": self.code.value,
            "error_severity": self.severity.value,
            "error_nature": self.nature.value,
            "error_message": self.message,
            "failed_action": self.action
        })

    @classmethod
    def unserialize(cls, error: str):
        error = json.loads(error)
        error_code = ErrorCode(error["error_code"])
        error_severity = ErrorSeverity(error["error_severity"])
        error_nature = ErrorNature(error["error_nature"])
        error_message = error["error_message"]
        failed_action = error["failed_action"]
        return cls(error_code, error_severity, error_nature, error_message, failed_action)
