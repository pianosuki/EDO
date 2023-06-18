from .message import IRCMessage


class IRCNegotiation:
    def __init__(self):
        self.history = []
        self.step = 0

    def log(self, message: IRCMessage):
        self.history.append(message)

    def progress(self, steps: int = 1):
        self.step += steps

    def regress(self, steps: int = 1):
        self.step -= steps
