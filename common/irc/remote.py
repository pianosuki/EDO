import asyncio
from .capabilities import IRCCapabilities
from .negotiation import IRCNegotiation


class StreamRemote:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.address = writer.get_extra_info("peername")
        self.cap = IRCCapabilities(mode="remote")
        self.negotiations = {}
        self.identity = {}
        self.info = {}

    def begin_negotiation(self, topic: str):
        if topic not in self.negotiations:
            self.negotiations[topic] = IRCNegotiation()

    def finish_negotiation(self, topic: str):
        if topic in self.negotiations:
            del self.negotiations[topic]

    def get_negotiation(self, topic: str):
        if topic not in self.negotiations:
            self.begin_negotiation(topic)
        return self.negotiations[topic]

    @property
    def nick(self):
        return self.info.get("nick", None)

    @nick.setter
    def nick(self, value):
        self.info["nick"] = str(value)

    @property
    def username(self):
        return self.info.get("username", None)

    @username.setter
    def username(self, value):
        self.info["username"] = str(value)

    @property
    def password(self):
        return self.info.get("access_token", None)

    @password.setter
    def password(self, value):
        self.info["access_token"] = str(value)
