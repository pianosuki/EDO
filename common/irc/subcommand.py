from enum import Enum, auto


class CapSubCommand(Enum):
    UNKNOWN = 0
    LS = auto()
    LIST = auto()
    REQ = auto()
    ACK = auto()
    NAK = auto()
    END = auto()
    NEW = auto()
    DEL = auto()
