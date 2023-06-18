import asyncio, traceback, aiohttp, base64, binascii
from typing import Optional
from common.irc import IRCMessage, IRCCapabilities, MessageCommand, CapSubCommand, StreamRemote
from common.lib import generate_pseudo_uuid
from config import AUTHENTICATION_SERVER, IRC_CAPABILITIES


class IRCServer:
    def __init__(self, **kwargs):
        self.host = kwargs.get("host", "127.0.0.1")
        self.port = kwargs.get("port", 6667)
        self.hostname = globals().get("HOSTNAME", self.host)
        self.auth_mode = kwargs.get("auth_mode", True)

        self.clients = set()
        self.users = {}  # Mapping of self.clients to dictionaries of their user data
        self.tasks = {}  # Mapping of self.clients to dictionaries of their tasks
        self.queues = {}  # Mapping of self.clients to dictionaries of their queues
        self.tokens = {}  # Mapping of access tokens to User UUIDs from the Authentication Server
        self.cap = IRCCapabilities(mode="local", capabilities=IRC_CAPABILITIES)

    @property
    def prefix(self):
        return self.hostname

    async def run(self):
        server = await asyncio.start_server(self.handle_connection, self.host, self.port)
        async with server:
            print(f"[{self.__class__.__name__}] Started the server!")
            await server.serve_forever()

    async def handle_connection(self, reader, writer):
        client = StreamRemote(reader, writer)
        try:
            print(f"[{self.__class__.__name__}] Adding client: {client.address}")
            self.clients.add(client)
            self.users[client] = {}
            self.tasks[client] = {}
            self.queues[client] = {}
            await self.handle_client(client)
        except ConnectionAbortedError as e:
            print(f"[{self.__class__.__name__}] ERROR:", type(e).__name__, e)
        except ConnectionResetError as e:
            print(f"[{self.__class__.__name__}] ERROR:", type(e).__name__, e)
        except Exception as e:
            print(f"[{self.__class__.__name__}] ERROR:", type(e).__name__, e)
            traceback.print_exc()
        finally:
            print(f"[{self.__class__.__name__}] Removing client: {client.address}")
            await self.handle_disconnection(client)
            self.clients.remove(client)
            for task in self.tasks[client].values():
                task.cancel()
            del self.users[client]
            del self.tasks[client]
            del self.queues[client]

    async def handle_disconnection(self, client: StreamRemote):
        pass

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

    async def handle_client(self, client: StreamRemote):
        self.queues[client]["inbound_queue"] = asyncio.Queue()
        self.queues[client]["outbound_queue"] = asyncio.Queue()
        self.tasks[client]["pull_task"] = asyncio.create_task(self.pull_task(client))
        self.tasks[client]["push_task"] = asyncio.create_task(self.push_task(client))
        self.tasks[client]["handler_task"] = asyncio.create_task(self.handle_message(client))
        await asyncio.gather(self.tasks[client]["pull_task"], self.tasks[client]["push_task"], self.tasks[client]["handler_task"])

    async def send(self, client: StreamRemote, message: IRCMessage):
        client.writer.write(message.serialize().encode())
        await client.writer.drain()

    async def recv(self, client: StreamRemote) -> Optional[IRCMessage]:
        data = await client.reader.readline()
        if data:
            message_string = data.decode().strip()
            return IRCMessage.deserialize(message_string)
        else:
            raise ConnectionResetError("Connection unexpectedly lost with client")

    async def pull_task(self, client: StreamRemote):
        """ PULL TASK """
        while True:
            message = await self.recv(client)
            print(f"[{self.__class__.__name__}] Received message from {client.address}: {str(message)}")
            await self.queues[client]["inbound_queue"].put(message)

    async def push_task(self, client: StreamRemote):
        """ PUSH TASK """
        while True:
            message = await self.queues[client]["outbound_queue"].get()
            await self.send(client, message)
            print(f"[{self.__class__.__name__}] Sent message to {client.address}: {str(message)}")

    async def handle_message(self, client: StreamRemote):
        while True:
            message = await self.queues[client]["inbound_queue"].get()
            match message.command:
                case MessageCommand.CAP:
                    await self.handle_cap_message(client, message)
                case MessageCommand.AUTHENTICATE:
                    await self.handle_authenticate_message(client, message)
                case MessageCommand.PASS:
                    await self.handle_pass_message(client, message)
                case MessageCommand.NICK:
                    await self.handle_nick_message(client, message)
                case MessageCommand.USER:
                    await self.handle_user_message(client, message)
                case MessageCommand.PING:
                    # await self.handle_ping_message(client, message)
                    pass
                case MessageCommand.PONG:
                    # await self.handle_pong_message(client, message)
                    pass
                case MessageCommand.OPER:
                    # await self.handle_oper_message(client, message)
                    pass
                case MessageCommand.QUIT:
                    # await self.handle_quit_message(client, message)
                    pass
                case MessageCommand.ERROR:
                    # await self.handle_error_message(client, message)
                    pass
                case MessageCommand.JOIN:
                    # await self.handle_join_message(client, message)
                    pass
                case MessageCommand.PART:
                    # await self.handle_part_message(client, message)
                    pass
                case MessageCommand.TOPIC:
                    # await self.handle_topic_message(client, message)
                    pass
                case MessageCommand.NAMES:
                    # await self.handle_names_message(client, message)
                    pass
                case MessageCommand.LIST:
                    # await self.handle_list_message(client, message)
                    pass
                case MessageCommand.INVITE:
                    # await self.handle_invite_message(client, message)
                    pass
                case MessageCommand.KICK:
                    # await self.handle_kick_message(client, message)
                    pass
                case MessageCommand.MOTD:
                    # await self.handle_motd_message(client, message)
                    pass
                case MessageCommand.VERSION:
                    # await self.handle_version_message(client, message)
                    pass
                case MessageCommand.ADMIN:
                    # await self.handle_admin_message(client, message)
                    pass
                case MessageCommand.CONNECT:
                    # await self.handle_connect_message(client, message)
                    pass
                case MessageCommand.LUSERS:
                    # await self.handle_lusers_message(client, message)
                    pass
                case MessageCommand.TIME:
                    # await self.handle_time_message(client, message)
                    pass
                case MessageCommand.STATS:
                    # await self.handle_stats_message(client, message)
                    pass
                case MessageCommand.HELP:
                    # await self.handle_help_message(client, message)
                    pass
                case MessageCommand.INFO:
                    # await self.handle_info_message(client, message)
                    pass
                case MessageCommand.MODE:
                    # await self.handle_mode_message(client, message)
                    pass
                case MessageCommand.PRIVMSG:
                    # await self.handle_privmsg_message(client, message)
                    pass
                case MessageCommand.NOTICE:
                    # await self.handle_notice_message(client, message)
                    pass
                case MessageCommand.WHO:
                    # await self.handle_who_message(client, message)
                    pass
                case MessageCommand.WHOIS:
                    # await self.handle_whois_message(client, message)
                    pass
                case MessageCommand.WHOWAS:
                    # await self.handle_whowas_message(client, message)
                    pass
                case MessageCommand.KILL:
                    # await self.handle_kill_message(client, message)
                    pass
                case MessageCommand.REHASH:
                    # await self.handle_rehash_message(client, message)
                    pass
                case MessageCommand.RESTART:
                    # await self.handle_restart_message(client, message)
                    pass
                case MessageCommand.SQUIT:
                    # await self.handle_squit_message(client, message)
                    pass
                case MessageCommand.AWAY:
                    # await self.handle_away_message(client, message)
                    pass
                case MessageCommand.LINKS:
                    # await self.handle_links_message(client, message)
                    pass
                case MessageCommand.USERHOST:
                    # await self.handle_userhost_message(client, message)
                    pass
                case MessageCommand.WALLOPS:
                    # await self.handle_wallops_message(client, message)
                    pass
                case _:
                    await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} ERR_UNKNOWNCOMMAND * {message.command} :Unknown command"))

    async def handle_cap_message(self, client: StreamRemote, message: IRCMessage):
        negotiation = client.get_negotiation("capability")
        negotiation.log(message)
        match message.subcommand:
            case CapSubCommand.LS:
                filtered_capabilities = self.cap.filter_by_version(message.get_version())
                client.cap.update(filtered_capabilities)
                await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} CAP * LS :{client.cap.serialize()}"))
            case CapSubCommand.REQ:
                requested_extensions = message.trailing.split()
                if self.cap.validate_extensions(requested_extensions):
                    client.cap.update_extensions(requested_extensions)
                    await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} CAP * ACK :{message.trailing}"))
                else:
                    await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} CAP * NAK :{message.trailing}"))
            case CapSubCommand.END:
                client.finish_negotiation("capability")
            case _:
                pass

    async def handle_authenticate_message(self, client: StreamRemote, message: IRCMessage):
        if not client.identity:
            negotiation = client.get_negotiation("authentication")
            negotiation.log(message)
            match negotiation.step:
                case 0:
                    try:
                        mechanism = message.params[0]
                        if mechanism == "*":
                            await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} ERR_SASLABORTED {client.nick} :SASL authentication aborted"))
                        else:
                            if self.cap.validate_mechanism("sasl", mechanism):
                                negotiation.progress()
                                await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} AUTHENTICATE +"))
                            else:
                                await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} RPL_SASLMECHS {client.nick} {','.join(self.cap.get_mechanisms('sasl'))} :are available SASL mechanisms"))
                    except IndexError:
                        await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} RPL_SASLMECHS {client.nick} {','.join(self.cap.get_mechanisms('sasl'))} :are available SASL mechanisms"))
                case 1:
                    try:
                        encoded_credentials = message.params[0]
                        authorization_identity, authentication_identity, password = base64.b64decode(encoded_credentials).decode().split("\x00")
                        authenticated = await self.authenticate(password)
                        if authenticated:
                            client.identity.update({"access_token": password, "uuid": self.tokens[password]})
                            # TO-DO: Create and implement an authorization API to verify usernames against in-game character names
                            # For now, proceed with assuming the user is authorized to use their provided nickname/username
                            await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} RPL_LOGGEDIN {client.nick} {client.nick}!~{client.username}@{client.address[0]} {client.username} :You are now logged in as {client.username}"))
                            await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} RPL_SASLSUCCESS {client.nick} :SASL authentication successful"))
                        else:
                            await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} ERR_SASLFAIL {client.nick} :SASL authentication failed"))
                    except (IndexError, ValueError, binascii.Error, UnicodeDecodeError):
                        await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} ERR_SASLFAIL {client.nick} :SASL authentication failed"))
        else:
            await self.queues[client]["outbound_queue"].put(IRCMessage.deserialize(f":{self.prefix} ERR_SASLALREADY {client.nick} :Already authenticated"))

    async def handle_pass_message(self, client: StreamRemote, message: IRCMessage):
        client.password = message.params[0]

    async def handle_nick_message(self, client: StreamRemote, message: IRCMessage):
        client.nick = message.params[0]

    async def handle_user_message(self, client: StreamRemote, message: IRCMessage):
        client.username = message.params[0]

    async def handle_quit_message(self, client: StreamRemote, message: IRCMessage):
        raise ConnectionAbortedError("Connection terminated by client")


if __name__ == "__main__":
    irc_server = IRCServer(auth_mode=False)
    asyncio.run(irc_server.run())
