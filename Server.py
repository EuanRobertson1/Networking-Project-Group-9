import re
import socket
import string
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set

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
        self._write_state()

    def remove_client(self, client: "Client") -> None:
        self.members.discard(client)
        if not self.members:
            self.server.remove_channel(self)


class Client:
    __linesep_regexp = re.compile(rb"\r?\n")

    def __init__(self, server: "Server", s: Socket) -> None:
        self.server = server
        self.socket = s
        # irc_lower(Channel name) --> Channel
        self.channels: Dict[bytes, Channel] = {}
        self.nickname = b""
        self.user = b""
        self.realName = b""
        host, port, _, _ = s.getpeername()
        self.host = host.encode()
        self.port = port
        self.__timestamp = time.time()
        self.__readBuffer = b""
        self.__writeBuffer = b""
        self.__sent_ping = False
        self.__handle_command = self.__registration_handler

    @property
    def prefix(self) -> bytes:
        return b"%s!%s@%s" % (self.nickname, self.user, self.host)

    def check_aliveness(self) -> None:
        now = time.time()
        if self.__timestamp + 180 < now:
            self.disconnect("ping timeout")
            return
        if not self.__sent_ping and self.__timestamp + 90 < now:
            if self.__handle_command == self.__command_handler:
                # Registered.
                self.message(b"PING :%s" % self.server.name)
                self.__sent_ping = True
            else:
                # Not registered.
                self.disconnect("ping timeout")

    def write_queue_size(self) -> int:
        return len(self.__writeBuffer)

    def __parse_read_buffer(self) -> None:
        lines = self.__linesep_regexp.split(self.__readBuffer)
        self.__readBuffer = lines[-1]
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

    def __registration_handler(
            self, command: bytes, arguments: Sequence[bytes]
    ) -> None:
        server = self.server
        if command == b"NICK":
            if len(arguments) < 1:
                self.reply(b"431 :No nickname given")
                return
            nick = arguments[0]
            if server.get_client(nick):
                self.reply(b"433 * %s :Nickname is already in use" % nick)
            else:
                self.nickname = nick
                server.client_changed_nickname(self, None)
        elif command == b"USER":
            if len(arguments) < 4:
                self.reply_461(b"USER")
                return
            self.user = arguments[0]
            self.realName = arguments[3]
        elif command == b"QUIT":
            self.disconnect("Client quit")
            return
        if self.nickname and self.user:
            self.reply(b"001 %s :Hi, welcome to IRC" % self.nickname)
            self.__handle_command = self.__command_handler

    def __send_names(
            self, arguments: Sequence[bytes], for_join: bool = False
    ) -> None:
        server = self.server
        if len(arguments) > 0:
            channelNames = arguments[0].split(b",")
        else:
            channelNames = sorted(self.channels.keys())
        for i, channelName in enumerate(channelNames):
            if for_join and irc_lower(channelName) in self.channels:
                continue
            channel = server.get_channel(channelName)

            if for_join:
                channel.add_member(self)
                self.channels[irc_lower(channelName)] = channel
                self.message_channel(channel, b"JOIN", channelName, True)


    def __command_handler(
            self, command: bytes, arguments: Sequence[bytes]
    ) -> None:
        def away_handler() -> None:
            pass

        def join_handler() -> None:
            if len(arguments) < 1:
                self.reply_461(b"JOIN")
                return
            if arguments[0] == b"0":
                for (channelName, channel) in self.channels.items():
                    self.message_channel(channel, b"PART", channelName, True)
                    server.remove_member_from_channel(self, channelName)
                self.channels = {}
                return
            self.__send_names(arguments, for_join=True)

        def names_handler() -> None:
            self.__send_names(arguments)

        def nick_handler() -> None:
            if len(arguments) < 1:
                self.reply(b"431 :No nickname given")
                return
            newNick = arguments[0]
            client = server.get_client(newNick)
            if newNick == self.nickname:
                pass
            elif client and client is not self:
                self.reply(
                    b"433 %s %s :Nickname is already in use"
                    % (self.nickname, newNick)
                )
            else:
                for x in self.channels.values():
                    self.channel_log(
                        x, b"changed nickname to %s" % newNick, meta=True
                    )
                oldNickname = self.nickname
                self.nickname = newNick
                server.client_changed_nickname(self, oldNickname)
                self.message_related(
                    b":%s!%s@%s NICK %s"
                    % (oldNickname, self.user, self.host, self.nickname),
                    True,
                )

        def notice_and_privmsg_handler() -> None:
            targetname = arguments[0]
            message = arguments[1]
            client = server.get_client(targetname)
            if client:
                client.message(
                    b":%s %s %s :%s"
                    % (self.prefix, command, targetname, message)
                )
            elif server.has_channel(targetname):
                channel = server.get_channel(targetname)
                self.message_channel(
                    channel, command, b"%s :%s" % (channel.name, message)
                )

            else:
                self.reply(
                    b"401 %s %s :No such nick/channel"
                    % (self.nickname, targetname)
                )

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
            b"NAMES": names_handler,
            b"NICK": nick_handler,
            b"NOTICE": notice_and_privmsg_handler,
            b"PING": ping_handler,
            b"PONG": pong_handler,
            b"PRIVMSG": notice_and_privmsg_handler,
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
            data = self.socket.recv(2 ** 10)
            quitmsg = "EOT"
        except socket.error as e:
            data = b""
            quitmsg = str(e)
        if data:
            self.__readBuffer += data
            self.__parse_read_buffer()
            self.__timestamp = time.time()
            self.__sent_ping = False
        else:
            self.disconnect(quitmsg)

    def socket_writable_notification(self) -> None:
        try:
            sent = self.socket.send(self.__writeBuffer)
            self.__writeBuffer = self.__writeBuffer[sent:]
        except socket.error as x:
            self.disconnect(str(x))

    def disconnect(self, quitmsg: str) -> None:
        self.message(f"ERROR :{quitmsg}".encode())
        host = self.host.decode(errors="ignore")
        self.server.print_info(
            f"Disconnected connection from {host}:{self.port} ({quitmsg})."
        )
        self.socket.close()
        self.server.remove_client(self, quitmsg.encode())

    def message(self, msg: bytes) -> None:
        self.__writeBuffer += msg + b"\r\n"

    def reply(self, msg: bytes) -> None:
        self.message(b":%s %s" % (self.server.name, msg))

    def reply_403(self, channel: bytes) -> None:
        self.reply(b"403 %s %s :No such channel" % (self.nickname, channel))

    def reply_461(self, command: bytes) -> None:
        nickname = self.nickname or b"*"
        self.reply(b"461 %s %s :Not enough parameters" % (nickname, command))

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
        server_name_limit = 63  # From the RFC.
        self.channels: Dict[bytes, Channel] = {}  # key: irc_lower(channelname)
        self.clients: Dict[Socket, Client] = {}
        self.nicknames: Dict[bytes, Client] = {}  # key: irc_lower(nickname)
        self.name = socket.getfqdn(self.address)[:server_name_limit].encode()


    def get_client(self, nickname: bytes) -> Optional[Client]:
        return self.nicknames.get(irc_lower(nickname))

    def has_channel(self, name: bytes) -> bool:
        return irc_lower(name) in self.channels

    def get_channel(self, channelname: bytes) -> Channel:
        if irc_lower(channelname) in self.channels:
            channel = self.channels[irc_lower(channelname)]
        else:
            channel = Channel(self, channelname)
            self.channels[irc_lower(channelname)] = channel
        return channel

    def print_info(self, msg: str) -> None:
        print(msg)
        sys.stdout.flush()

    def client_changed_nickname(
            self, client: Client, oldnickname: Optional[bytes]
    ) -> None:
        if oldnickname:
            del self.nicknames[irc_lower(oldnickname)]
        self.nicknames[irc_lower(client.nickname)] = client

    def remove_member_from_channel(
            self, client: Client, channelname: bytes
    ) -> None:
        if irc_lower(channelname) in self.channels:
            channel = self.channels[irc_lower(channelname)]
            channel.remove_client(client)

    def remove_client(self, client: Client, quitmsg: bytes) -> None:
        client.message_related(b":%s QUIT :%s" % (client.prefix, quitmsg))
        for x in client.channels.values():
            x.remove_client(client)
        if client.nickname and irc_lower(client.nickname) in self.nicknames:
            del self.nicknames[irc_lower(client.nickname)]
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
            iwtd, owtd, ewtd = select.select(
                serversockets + [x.socket for x in self.clients.values()],
                [x.socket for x in self.clients.values()
                 if x.write_queue_size() > 0
                 ],
                [],
                10,
            )
            for x in iwtd:
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
            for x in owtd:
                if x in self.clients:  # client may have been disconnected
                    self.clients[x].socket_writable_notification()
            now = time.time()
            if last_aliveness_check + 10 < now:
                for client in list(self.clients.values()):
                    client.check_aliveness()
                last_aliveness_check = now


_ircstring_translation = bytes.maketrans(
    (string.ascii_lowercase.upper() + "[]\\^").encode(),
    (string.ascii_lowercase + "{}|~").encode(),
)


def irc_lower(s: bytes) -> bytes:
    return s.translate(_ircstring_translation)


def main() -> None:
    server = Server()
    server.start()


main()
