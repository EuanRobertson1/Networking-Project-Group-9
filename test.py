import logging
import os
import re
import select
import socket
import string
import sys
import tempfile
import time

from argparse import ArgumentParser, Namespace
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Sequence, Set

Socket = socket.socket

VERSION = "2.1"


def create_directory(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path)


class Channel:
    def __init__(self, server: "Server", name: bytes) -> None:
        self.server = server
        self.name = name
        self.members: Set["Client"] = set()
        self._topic = b""
        self._key: Optional[bytes] = None
        self._state_path: Optional[str]
        if self.server.state_dir:
            fs_safe_name = (
                name.decode(errors="ignore")
                .replace("_", "__")
                .replace("/", "_")
            )
            self._state_path = f"{self.server.state_dir}/{fs_safe_name}"
            self._read_state()
        else:
            self._state_path = None

    def add_member(self, client: "Client") -> None:
        self.members.add(client)

    @property
    def topic(self) -> bytes:
        return self._topic

    @topic.setter
    def topic(self, value: bytes) -> None:
        self._topic = value
        self._write_state()

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

    def _read_state(self) -> None:
        if not (self._state_path and os.path.exists(self._state_path)):
            return
        data: Dict[str, Any] = {}

        with open(self._state_path, "rb") as state_file:
            exec(state_file.read(), {}, data)

        self._topic = data.get("topic", "")
        self._key = data.get("key")

    def _write_state(self) -> None:
        if not self._state_path:
            return
        fd, path = tempfile.mkstemp(dir=os.path.dirname(self._state_path))
        fp = os.fdopen(fd, "w")
        fp.write("topic = %r\n" % self.topic)
        fp.write("key = %r\n" % self.key)
        fp.close()
        os.replace(path, self._state_path)


class Client:
    __linesep_regexp = re.compile(rb"\r?\n")
    # The RFC limit for nicknames is 9 characters, but what the heck.
    __valid_nickname_regexp = re.compile(
        rb"^[][\`_^{|}A-Za-z][][\`_^{|}A-Za-z0-9-]{0,50}$"
    )
    __valid_channelname_regexp = re.compile(
        rb"^[&#+!][^\x00\x07\x0a\x0d ,:]{0,50}$"
    )

    def __init__(self, server: "Server", socket: Socket) -> None:
        self.server = server
        self.socket = socket
        self.channels: Dict[bytes, Channel] = {}
        self.nickname = b""
        self.user = b""
        self.realname = b""
        if self.server.ipv6:
            host, port, _, _ = socket.getpeername()
        else:
            host, port = socket.getpeername()
        self.host = host.encode()
        self.port = port
        self.__timestamp = time.time()
        self.__readbuffer = b""
        self.__writebuffer = b""
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
        return len(self.__writebuffer)

    def __parse_read_buffer(self) -> None:
        lines = self.__linesep_regexp.split(self.__readbuffer)
        self.__readbuffer = lines[-1]
        lines = lines[:-1]
        for line in lines:
            if not line:
                continue
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
            elif not self.__valid_nickname_regexp.match(nick):
                self.reply(b"432 * %s :Erroneous nickname" % nick)
            else:
                self.nickname = nick
                server.client_changed_nickname(self, None)
        elif command == b"USER":
            if len(arguments) < 4:
                self.reply_461(b"USER")
                return
            self.user = arguments[0]
            self.realname = arguments[3]
        elif command == b"QUIT":
            self.disconnect("Client quit")
            return
        if self.nickname and self.user:
            self.send_motd()
            self.__handle_command = self.__command_handler

    def __send_names(
            self, arguments: Sequence[bytes], for_join: bool = False
    ) -> None:
        server = self.server
        valid_channel_re = self.__valid_channelname_regexp
        if len(arguments) > 0:
            channelnames = arguments[0].split(b",")
        else:
            channelnames = sorted(self.channels.keys())
        if len(arguments) > 1:
            keys = arguments[1].split(b",")
        else:
            keys = []
        for i, channelname in enumerate(channelnames):
            if for_join and irc_lower(channelname) in self.channels:
                continue
            if not valid_channel_re.match(channelname):
                self.reply_403(channelname)
                continue
            channel = server.get_channel(channelname)
            if channel.key is not None and (
                    len(keys) <= i or channel.key != keys[i]
            ):
                self.reply(
                    b"475 %s %s :Cannot join channel (+k) - bad key"
                    % (self.nickname, channelname)
                )
                continue

            if for_join:
                channel.add_member(self)
                self.channels[irc_lower(channelname)] = channel
                self.message_channel(channel, b"JOIN", channelname, True)
                self.channel_log(channel, b"joined", meta=True)
                if channel.topic:
                    self.reply(
                        b"332 %s %s :%s"
                        % (self.nickname, channel.name, channel.topic)
                    )
                else:
                    self.reply(
                        b"331 %s %s :No topic is set"
                        % (self.nickname, channel.name)
                    )
            names_prefix = b"353 %s = %s :" % (self.nickname, channelname)
            names = b""
            # Max length: reply prefix ":server_name(space)" plus CRLF in
            # the end.
            names_max_len = 512 - (len(server.name) + 2 + 2)
            for name in sorted(x.nickname for x in channel.members):
                if not names:
                    names = names_prefix + name
                # Using >= to include the space between "names" and "name".
                elif len(names) + len(name) >= names_max_len:
                    self.reply(names)
                    names = names_prefix + name
                else:
                    names += b" " + name
            if names:
                self.reply(names)
            self.reply(
                b"366 %s %s :End of NAMES list" % (self.nickname, channelname)
            )

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
                for (channelname, channel) in self.channels.items():
                    self.message_channel(channel, b"PART", channelname, True)
                    self.channel_log(channel, b"left", meta=True)
                    server.remove_member_from_channel(self, channelname)
                self.channels = {}
                return
            self.__send_names(arguments, for_join=True)

        def nick_handler() -> None:
            if len(arguments) < 1:
                self.reply(b"431 :No nickname given")
                return
            newnick = arguments[0]
            client = server.get_client(newnick)
            if newnick == self.nickname:
                pass
            elif client and client is not self:
                self.reply(
                    b"433 %s %s :Nickname is already in use"
                    % (self.nickname, newnick)
                )
            elif not self.__valid_nickname_regexp.match(newnick):
                self.reply(
                    b"432 %s %s :Erroneous Nickname" % (self.nickname, newnick)
                )
            else:
                for x in self.channels.values():
                    self.channel_log(
                        x, b"changed nickname to %s" % newnick, meta=True
                    )
                oldnickname = self.nickname
                self.nickname = newnick
                server.client_changed_nickname(self, oldnickname)
                self.message_related(
                    b":%s!%s@%s NICK %s"
                    % (oldnickname, self.user, self.host, self.nickname),
                    True,
                )

        def notice_and_privmsg_handler() -> None:
            if len(arguments) == 0:
                self.reply(
                    b"411 %s :No recipient given (%s)"
                    % (self.nickname, command)
                )
                return
            if len(arguments) == 1:
                self.reply(b"412 %s :No text to send" % self.nickname)
                return
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
                self.channel_log(channel, message)
            else:
                self.reply(
                    b"401 %s %s :No such nick/channel"
                    % (self.nickname, targetname)
                )

        def ping_handler() -> None:
            if len(arguments) < 1:
                self.reply(b"409 %s :No origin specified" % self.nickname)
                return
            self.reply(b"PONG %s :%s" % (server.name, arguments[0]))

        def pong_handler() -> None:
            pass

        def quit_handler() -> None:
            if len(arguments) < 1:
                quitmsg = self.nickname
            else:
                quitmsg = arguments[0]

        handler_table = {
            b"AWAY": away_handler,
            b"JOIN": join_handler,
            b"NICK": nick_handler,
            b"NOTICE": notice_and_privmsg_handler,
            b"PING": ping_handler,
            b"PONG": pong_handler,
            b"PRIVMSG": notice_and_privmsg_handler,
            b"QUIT": quit_handler,

        }
        server = self.server
        valid_channel_re = self.__valid_channelname_regexp
        try:
            handler_table[command]()
        except KeyError:
            self.reply(
                b"421 %s %s :Unknown command" % (self.nickname, command)
            )

    def socket_readable_notification(self) -> None:
        try:
            data = self.socket.recv(2 ** 10)
            if self.server.debug:
                host = self.host.decode(errors="ignore")
                self.server.print_debug(f"[{host}:{self.port}] -> {data!r}")
            quitmsg = "EOT"
        except socket.error as e:
            data = b""
            quitmsg = str(e)
        if data:
            self.__readbuffer += data
            self.__parse_read_buffer()
            self.__timestamp = time.time()
            self.__sent_ping = False

    def socket_writable_notification(self) -> None:
        try:
            sent = self.socket.send(self.__writebuffer)
            if self.server.debug:
                head = self.__writebuffer[:sent]
                host = self.host.decode(errors="ignore")
                self.server.print_debug(f"[{host}:{self.port}] <- {head!r}")
            self.__writebuffer = self.__writebuffer[sent:]
        except socket.error as x:
            self.disconnect(str(x))

    def message(self, msg: bytes) -> None:
        self.__writebuffer += msg + b"\r\n"

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

    def channel_log(
            self, channel: Channel, message: bytes, meta: bool = False
    ) -> None:
        if not self.server.channel_log_dir:
            return
        if meta:
            format_string = "[{}] * {} {}\n"
        else:
            format_string = "[{}] <{}> {}\n"
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        channel_name = irc_lower(channel.name).decode(errors="ignore")
        logname = channel_name.replace("_", "__").replace("/", "_")
        logfile = f"{self.server.channel_log_dir}/{logname}.log"
        logmsg = format_string.format(timestamp, self.nickname, message)
        with open(logfile, "a") as fp:
            fp.write(logmsg)

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

    def send_motd(self) -> None:
        server = self.server

        self.reply(
            b"375 %s :- %s Group project team 9 -"
            % (self.nickname, server.name)
        )


class Server:
    def __init__(self, args: Namespace) -> None:
        self.ports = args.ports
        self.password: str = args.password
        self.ipv6 = args.ipv6
        self.debug = args.debug
        self.channel_log_dir = args.channel_log_dir
        self.state_dir = args.state_dir
        self.log_file = args.log_file
        self.log_count = args.log_count
        self.logger: Optional[logging.Logger] = None
        self.name: bytes

        if args.listen and self.ipv6:
            self.address = socket.getaddrinfo(
                args.listen, None, proto=socket.IPPROTO_TCP
            )[0][4][0]
        elif args.listen:
            self.address = socket.gethostbyname(args.listen)
        else:
            self.address = ""
        server_name_limit = 63  # From the RFC.
        self.name = socket.getfqdn(self.address)[:server_name_limit].encode()

        self.channels: Dict[bytes, Channel] = {}  # key: irc_lower(channelname)
        self.clients: Dict[Socket, Client] = {}
        self.nicknames: Dict[bytes, Client] = {}  # key: irc_lower(nickname)
        if self.channel_log_dir:
            create_directory(self.channel_log_dir)
        if self.state_dir:
            create_directory(self.state_dir)

    def make_pid_file(self, filename: str) -> None:
        try:
            fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o644)
            os.write(fd, b"%i\n" % os.getpid())
            os.close(fd)
        except Exception:
            self.print_error("Could not create PID file %r" % filename)
            sys.exit(1)

    def remove_pid_file(self, filename: str) -> None:
        try:
            os.remove(filename)
        except Exception:
            self.print_error("Could not remove PID file %r" % filename)

    def daemonize(self) -> None:
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError:
            sys.exit(1)
        os.setsid()
        try:
            pid = os.fork()
            if pid > 0:
                self.print_info("PID: %d" % pid)
                sys.exit(0)
        except OSError:
            sys.exit(1)
        os.chdir("/")
        os.umask(0)
        dev_null = open("/dev/null", "r+")
        os.dup2(dev_null.fileno(), sys.stdout.fileno())
        os.dup2(dev_null.fileno(), sys.stderr.fileno())
        os.dup2(dev_null.fileno(), sys.stdin.fileno())

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

    def print_debug(self, msg: str) -> None:
        if self.debug:
            print(msg)
            sys.stdout.flush()
            if self.logger:
                self.logger.debug(msg)

    def print_error(self, msg: str) -> None:
        sys.stderr.write(f"{msg}\n")
        if self.logger:
            self.logger.error(msg)

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
            client.channel_log(x, b"quit (%s)" % quitmsg, meta=True)
            x.remove_client(client)
        if client.nickname and irc_lower(client.nickname) in self.nicknames:
            del self.nicknames[irc_lower(client.nickname)]
        del self.clients[client.socket]

    def remove_channel(self, channel: Channel) -> None:
        del self.channels[irc_lower(channel.name)]

    def start(self) -> None:
        serversockets = []
        for port in self.ports:
            s = socket.socket(
                socket.AF_INET6 if self.ipv6 else socket.AF_INET,
                socket.SOCK_STREAM,
            )
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((self.address, port))
            except socket.error as e:
                self.print_error(f"Could not bind port {port}: {e}.")
                sys.exit(1)
            s.listen(5)
            serversockets.append(s)
            del s

        self.init_logging()
        try:
            self.run(serversockets)
        except Exception:
            if self.logger:
                self.logger.exception("Fatal exception")
            raise

    def init_logging(self) -> None:
        if not self.log_file:
            return

        log_level = logging.INFO
        if self.debug:
            log_level = logging.DEBUG
        self.logger = logging.getLogger("miniircd")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s[%(process)d] - %(levelname)s - %(message)s"
        )
        fh = RotatingFileHandler(
            self.log_file,
            maxBytes=self.log_max_bytes,
            backupCount=self.log_count,
        )
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        self.logger.setLevel(log_level)
        self.logger.addHandler(fh)

    def run(self, serversockets: List[Socket]) -> None:
        last_aliveness_check = time.time()
        while True:
            iwtd, owtd, ewtd = select.select(
                serversockets + [x.socket for x in self.clients.values()],
                [
                    x.socket
                    for x in self.clients.values()
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
    ap = ArgumentParser(
        description="Group project 9",
    )
    ap.add_argument("--version", action="version", version=VERSION)
    ap.add_argument(
        "--channel-log-dir",
        metavar="X",
        help="store channel log in directory X",
    )
    ap.add_argument(
        "-d", "--daemon", action="store_true", help="fork and become a daemon"
    )
    ap.add_argument("--ipv6", action="store_true", help="use IPv6")
    ap.add_argument(
        "--debug", action="store_true", help="print debug messages to stdout"
    )
    ap.add_argument(
        "--listen", metavar="X", help="listen on specific IP address X"
    )
    ap.add_argument(
        "--log-count",
        metavar="X",
        default=10,
        type=int,
        help="keep X log files; default: %(default)s",
    )
    ap.add_argument("--log-file", metavar="X", help="store log in file X")
    ap.add_argument(
        "-p",
        "--password",
        metavar="X",
        help="require connection password X; default: no password",
    )
    ap.add_argument(
        "--ports",
        metavar="X",
        help="listen to ports X (a list separated by comma or whitespace);"
             " default: 6667 or 6697 if SSL is enabled",
    )
    ap.add_argument(
        "--state-dir",
        metavar="X",
        help="save persistent channel state (topic, key) in directory X",
    )

    args = ap.parse_args()

    if args.ports is None:
        args.ports = "6667"

    if (
            os.name == "posix"
            and not args.setuid
            and (os.getuid() == 0 or os.getgid() == 0)
    ):
        ap.error(
            "Running this service as root is not recommended."
        )

    ports = []
    for port in re.split(r"[,\s]+", args.ports):
        try:
            ports.append(int(port))
        except ValueError:
            ap.error("bad port: %r" % port)
    args.ports = ports
    server = Server(args)
    try:
        server.start()
    except KeyboardInterrupt:
        server.print_error("Interrupted.")


if __name__ == "__main__":
    main()
