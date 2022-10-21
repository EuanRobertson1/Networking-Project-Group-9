import re
import socket
import sys
import time
from typing import Dict, List, Optional, Sequence, Set

import select

Socket = socket.socket


class Channel:
    def __init__(self, server: "Server", name: bytes) -> None:
        self.server = server
        self.name = name
        self.members: Set["Client"] = set()
        self._key: Optional[bytes] = None
        self._state_path: Optional[str]
        self._state_path = None

    def add_member(self, client: "Client") -> None:
        self.members.add(client)

    @property
    def key(self) -> Optional[bytes]:
        return self._key

    @key.setter
    def key(self, value: bytes) -> None:
        self._key = value

    def remove_client(self, client: "Client") -> None:
        self.members.discard(client)


class Client:
    __linesep_regexp = re.compile(rb"\r?\n")

    def __init__(self, server: "Server", s: Socket) -> None:
        self.server = server
        self.socket = s
        self.channels: Dict[bytes, Channel] = {}
        self.nickname = b""
        self.user = b""
        self.realName = b""
        host, port, _, _ = s.getpeername()
        self.host = host.encode()
        self.port = port
        self.__timestamp = time.time()
        self._recv_buffer = b""
        self._send_buffer = b""
        self.__sent_ping = False
        self.__handle_command = self._register_user_handler

    @property
    def prefix(self) -> bytes:
        return b"%s!%s@%s" % (self.nickname, self.user, self.host)

    def user_ping(self) -> None:
        if not self.__sent_ping and self.__timestamp + 90 < time.time():
            # Checks if user is registered
            if self.__handle_command == self.__command_handler:
                # Pings the user, and it saves that it pinged him correctly so the next cycle starts
                self.message(b"PING :%s" % self.server.name)
                self.__sent_ping = True

    def user_afk(self) -> None:
        if self.__timestamp + 180 < time.time():
            self.disconnect("Dont stay afk next time")
            return

    def write_queue_size(self) -> int:
        return len(self._send_buffer)

    def _read_buffer(self) -> None:
        lines = self.__linesep_regexp.split(self._recv_buffer)
        self._recv_buffer = lines[-1]
        lines = lines[:-1]
        for line in lines:
            x = line.split(b" ", 1)
            command = x[0].upper()
            if len(x) == 1:
                arguments = []
            elif x[1].startswith(b":"):
                arguments = [x[1][1:]]
            else:
                y = x[1].split(b" :", 1)
                arguments = y[0].split()
                if len(y) == 2:
                    arguments.append(y[1])
            self.__handle_command(command, arguments)

    def _register_user_handler(
            self, command: bytes, arguments: Sequence[bytes]
    ) -> None:
        server = self.server
        command = command.decode("utf-8")
        if command == "NICK":
            nick = arguments[0]
            if server.get_client(nick):
                self.reply(b"2 * %s : Someone is using this Nickname, please use /nick to change your nickname" % nick)
            else:
                self.nickname = nick
                server.client_changed_nickname(self, None)
        elif command == "USER":
            self.user = arguments[0]
            self.realName = arguments[3]
        elif command == "QUIT":
            self.disconnect("Bye Bye")
            return
        if self.nickname and self.user:
            self.reply(b"1 %s :Hi, welcome to Group Project 9" % self.nickname)
            self.__handle_command = self.__command_handler

    def __send_names(
            self, arguments: Sequence[bytes], join_channel: bool = False
    ) -> None:
        server = self.server
        channelNames = arguments[0].split(b",")
        for i, channelName in enumerate(channelNames):
            if join_channel and channelName in self.channels:
                continue
            channel = server.get_channel(channelName)

            if join_channel:
                channel.add_member(self)
                self.channels[channelName] = channel
                self.message_channel(channel, b"JOIN", channelName, True)

    def __command_handler(
            self, command: bytes, arguments: Sequence[bytes]
    ) -> None:
        def away_handler() -> None:
            pass

        def join_handler() -> None:
            if len(arguments) < 1:
                self.reply(b"431 :Please use the following format /join #<name>")
                return
            if arguments[0] == b"0":
                for (channelName, channel) in self.channels.items():
                    self.message_channel(channel, b"PART", channelName, True)
                    server.remove_member_from_channel(self, channelName)
                self.channels = {}
                return
            self.__send_names(arguments, join_channel=True)



        def msg_to_channel_and_pms() -> None:
            targetName = arguments[0]
            message = arguments[1]
            client = server.get_client(targetName)
            if client:
                client.message(b":%s %s %s :%s" % (self.prefix, command, targetName, message))
            elif server.channel_created_on_server(targetName):
                channel = server.get_channel(targetName)
                self.message_channel(channel, command, b"%s :%s" % (channel.name, message))

        def ping_handler() -> None:
            self.reply(b"PONG %s :%s" % (server.name, arguments[0]))

        def pong_handler() -> None:
            pass

        def quit_handler() -> None:
            if len(arguments) < 1:
                quitmsg = self.nickname
            else:
                quitmsg = arguments[0]
            self.disconnect(quitmsg.decode(errors="ignore"))

        handler_table = {
            b"AWAY": away_handler,
            b"JOIN": join_handler,
            b"NOTICE": msg_to_channel_and_pms,
            b"PING": ping_handler,
            b"PONG": pong_handler,
            b"PRIVMSG": msg_to_channel_and_pms,
            b"QUIT": quit_handler,
        }
        server = self.server
        try:
            handler_table[command]()
        except KeyError:
            self.reply(
                b"421 %s %s :Unknown command" % (self.nickname, command)
            )

    def socket_readable_notification(self) -> None:
        try:
            data = self.socket.recv(1024)
            quitmsg = "Bye bye"
        except socket.error as e:
            data = b""
            quitmsg = str(e)
        if data:
            self._recv_buffer += data
            self._read_buffer()
            self.__timestamp = time.time()
            self.__sent_ping = False
        else:
            self.disconnect(quitmsg)

    def socket_writable_notification(self) -> None:
        try:
            sent = self.socket.send(self._send_buffer)
            self._send_buffer = self._send_buffer[sent:]
        except socket.error as x:
            self.disconnect(str(x))

    def disconnect(self, quitmsg: str) -> None:
        self.message(f"ERROR :{quitmsg}".encode())
        host = self.host.decode(errors="ignore")
        self.server.print_info(f"Disconnected connection from {host}:{self.port} ({quitmsg}).")
        self.socket.close()
        self.server.remove_client(self, quitmsg.encode())

    def message(self, msg: bytes) -> None:
        self._send_buffer += msg + b"\r\n"

    def reply(self, msg: bytes) -> None:
        self.message(b":%s %s" % (self.server.name, msg))

    def message_channel(
            self,
            channel: Channel,
            command: bytes,
            message: bytes,
            include_self: bool = False,
    ) -> None:
        line = b":%s %s %s" % (self.prefix, command, message)
        for client in channel.members:
            if client != self or include_self:
                client.message(line)

    def message_related(self, msg: bytes, include_self: bool = False) -> None:
        clients = set()
        if include_self:
            clients.add(self)
        for channel in self.channels.values():
            clients |= channel.members
        if not include_self:
            clients.discard(self)
        for client in clients:
            client.message(msg)


class Server:
    def __init__(self) -> None:
        self.ports = 6667
        self.name: bytes
        self.address = "::1"
        self.state_dir = "X"
        self.channel_log_dir = "X"
        self.channels: Dict[bytes, Channel] = {}  # key: irc_lower(channelname)
        self.clients: Dict[Socket, Client] = {}
        self.nicknames: Dict[bytes, Client] = {}  # key: irc_lower(nickname)
        self.name = socket.getfqdn(self.address)[:5].encode()

    def get_client(self, nickname: bytes) -> Optional[Client]:
        return self.nicknames.get(nickname)

    def channel_created_on_server(self, name: bytes) -> bool:
        return name in self.channels

    def get_channel(self, channelname: bytes) -> Channel:
        if channelname in self.channels:
            channel = self.channels[channelname]
        else:
            channel = Channel(self, channelname)
            self.channels[channelname] = channel
        return channel

    def print_info(self, msg: str) -> None:
        print(msg)
        sys.stdout.flush()

    def client_changed_nickname(
            self, client: Client, oldnickname: Optional[bytes]
    ) -> None:
        if oldnickname:
            del self.nicknames[oldnickname]
        self.nicknames[client.nickname] = client

    def remove_member_from_channel(
            self, client: Client, channelname: bytes
    ) -> None:
        if channelname in self.channels:
            channel = self.channels[channelname]
            channel.remove_client(client)

    def remove_client(self, client: Client, quitmsg: bytes) -> None:
        client.message_related(b":%s QUIT :%s" % (client.prefix, quitmsg))
        for x in client.channels.values():
            x.remove_client(client)
        if client.nickname and client.nickname in self.nicknames:
            del self.nicknames[client.nickname]
        del self.clients[client.socket]

    def start(self) -> None:
        serversockets = []

        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.address, 6667))
        s.listen(5)
        serversockets.append(s)

        del s
        self.print_info(f"Listening on port 6667.")
        self.run(serversockets)

    def run(self, serversockets: List[Socket]) -> None:
        last_aliveness_check = time.time()
        while True:
            clients, client_action, ewtd = select.select(
                serversockets + [x.socket for x in self.clients.values()],
                [x.socket for x in self.clients.values()
                 if x.write_queue_size() > 0], [], 10)
            for x in clients:
                if x in self.clients:
                    self.clients[x].socket_readable_notification()
                else:
                    conn, addr = x.accept()
                    try:
                        self.clients[conn] = Client(self, conn)
                        self.print_info(
                            f"Accepted connection from {addr[0]}:{addr[1]}."
                        )
                    except socket.error:
                        try:
                            conn.close()
                        except Exception:
                            pass
            for x in client_action:
                if x in self.clients:
                    self.clients[x].socket_writable_notification()
            now = time.time()
            if last_aliveness_check + 10 < now:
                for client in list(self.clients.values()):
                    client.user_ping()
                    client.user_afk()
                last_aliveness_check = now


server = Server()
server.start()
