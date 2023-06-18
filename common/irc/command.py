from enum import Enum, auto
from typing import Iterable
from .subcommand import CapSubCommand


class MessageCommand(Enum):
    UNKNOWN = 0
    CAP = auto(), CapSubCommand
    AUTHENTICATE = auto()
    PASS = auto()
    NICK = auto()
    USER = auto()
    PING = auto()
    PONG = auto()
    OPER = auto()
    QUIT = auto()
    ERROR = auto()
    JOIN = auto()
    PART = auto()
    TOPIC = auto()
    NAMES = auto()
    LIST = auto()
    INVITE = auto()
    KICK = auto()
    MOTD = auto()
    VERSION = auto()
    ADMIN = auto()
    CONNECT = auto()
    LUSERS = auto()
    TIME = auto()
    STATS = auto()
    HELP = auto()
    INFO = auto()
    MODE = auto()
    PRIVMSG = auto()
    NOTICE = auto()
    WHO = auto()
    WHOIS = auto()
    WHOWAS = auto()
    KILL = auto()
    REHASH = auto()
    RESTART = auto()
    SQUIT = auto()
    AWAY = auto()
    LINKS = auto()
    USERHOST = auto()
    WALLOPS = auto()


    def __init__(self, value: int, lookup: Iterable = None):
        self._value = value
        self.lookup = lookup
