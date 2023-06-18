import re
from typing import Optional, Type, Any, Union
from .command import MessageCommand
from .numeric import MessageNumeric


class IRCMessage:

    def __init__(self, prefix: Optional[str], command: Union[MessageCommand, MessageNumeric], params: list, subcommand: Optional[Type[Any]], trailing: Optional[str]):
        self.prefix = prefix
        self.command = command
        self.params = params
        self.subcommand = subcommand
        self.trailing = trailing

    def __repr__(self):
        return "IRCMessage(prefix={}, command={}, params={}, subcommand={}, body={})".format(self.prefix, self.command, self.params, self.subcommand, self.trailing)

    def __str__(self):
        return repr(self.serialize())

    def serialize(self) -> str:
        prefix_string = f":{self.prefix} " if self.prefix else ""
        command_string = self.command.name if isinstance(self.command, MessageCommand) else (self.command.value if isinstance(self.command, MessageNumeric) else "UNKNOWN")
        params_string = " " + " ".join(self.params) if self.params else ""
        return "{}{}{}\r\n".format(prefix_string, command_string, params_string)

    @classmethod
    def deserialize(cls, message_string: str) -> "IRCMessage":
        pattern = r"(?::([^ ]+) +)?([^ ]+)(?: +(.+))?"
        match = re.match(pattern, message_string)
        if match:
            prefix = match.group(1)
            command = next((command for command in MessageCommand if command.name == match.group(2)), MessageCommand.UNKNOWN) if not re.search(r"^[A-Z]{3}_[A-Z]+$", match.group(2)) else next((numeric for numeric in MessageNumeric if numeric.name == match.group(2)), MessageNumeric.UNKNOWN)
            params_split = [param_half.strip() for param_half in match.group(3).split(":", 1)] if match.group(3) else None
            params = [param for param in [*params_split[0].strip().split(), ":" + params_split[1] if len(params_split) > 1 else ""] if param] if params_split else []
            subcommand = next((subcommand for subcommand in command.lookup if subcommand.name in params), None) if hasattr(command, "lookup") and command.lookup is not None else None
            trailing = params_split[1] if len(params_split) > 1 else None
            return cls(prefix=prefix, command=command, params=params, subcommand=subcommand, trailing=trailing)
        else:
            raise ValueError("Invalid IRC message format")

    def get_version(self) -> Optional[int]:
        return next((int(item) for item in self.params if re.search(r"^\d{3}$", item)), None)

    def get_mechanisms(self) -> Optional[list]:
        return next((item.split("=")[1].split(",") for item in self.params if re.search(r"^[^=]*=([^,]+,)+?[^,]+$", item)), None)
