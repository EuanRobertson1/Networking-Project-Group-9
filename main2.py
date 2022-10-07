import socket
import threading

Port = 6667
# Server ="0000:0000:0000:0000:0000:0000:0000:0001"
# ADDRESS = (Server, Port)
ADDRESS = ('localhost', Port)
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

print('Server Starting on {} port {}'.format(*ADDRESS))
sock.bind(ADDRESS)


# channel
class Channel:

    # initialise object attributes
    def __init__(self, name):
        self.name = name
        self.users = []

    # add client to list
    def join(self, user):
        self.users.append(user)
        for u in self.users:
            sendMSG(f'user {user.nickname} has joined the chat', u)

    # remove client
    def leave(self, user):
        self.users.remove(user)
        for u in self.users:
            sendMSG(f'user {user.nickname} has left the channel', u)

    # private message
    def privateMessageChannel(self, user, data):
        if data == "":
            return
        m = f"|private| {user.nickname}: {data}"


# Listen for messages
print('waiting for a Client Connection')




# create channel
class User:
    def __init__(self, socket, addr, username, nickname, realname):
        self.socket = socket
        self.address = addr
        self.username = username
        self.nickname = nickname
        self.realname = realname

#predefined channels
channels = [Channel("test"), Channel("unicorn")]


def connectUser(s):
    s.listen()
    while True:

        try:
            socket, addr = s.accept()
        except:
            print(f'{str(addr)} error connecting')

        print(f"{str(addr)} has connected")

        username = ""
        nickname = ""
        realname = ""

        while True:

            msg = socket.recv(1024).decode('utf-8')
            print(msg)

            if "USER" not in msg:
                socket.send("please set your nickname using /nick <your nickname>\n".encode('utf-8'))
                continue

            for c in channels:
                for u in c.users:
                    if u.username == username:
                        socket.send(f'sorry username {user} already taken, please try again'.encode('utf-8'))
                        continue

            cmd = msg.split()

            username = cmd[1]
            realname = cmd[4]

            socket.send("Username Valid".encode('utf-8'))

            break

        while True:
            msg = socket.recv(1024).decode('utf-8')
            print(msg)

            if "NICK" not in msg:
                socket.send("please enter a correct NICK command".encode('utf-8'))
                continue

            cmd = msg.split()
            nickname = cmd[1]

            break

        user = User(socket, addr, username, nickname, realname)

        thread = handleClient(user)
        thread.start()


# send messages
def sendMSG(msg, user):
    try:
        user.socket.send(msg.encode('utf-8'))
    except:
        user.socket.close()
        print(f'user {user.nickname} disconnected unexpectedly')
        for c in channels:
            for u in c.users:
                if u == user:
                    c.leave(user)
        exit()


# Client Commands
def listUserCommands():
    msg = "\nCOMMANDS"
    msg = msg + "\nJOIN - Join a Channel. You can only join #test and #unicorn"
    msg = msg + "\nPING - PING PONG"
    msg = msg + "\nPMMSG - private message to a Client"
    msg = msg + "\nEXIT - you exit\n"
    return msg


# join a channel
def join(user, msg):
    chanName = msg.strip().split()[1][1:]

    print(chanName)

    channel = None

    for c in channels:
        if c.name == chanName:
            channel = c

    if channel == None:
        sendMSG("\nPlease enter a valid channel name", user)
        return

    for c in channels:
        for u in c.users:
            if u == user:
                c.leave(user)

    channel.join(user)
    print(f'user {user.nickname} has has joined channel {channel.name}')


# private messages
def pm(user, msg):
    cmd = msg.split(":")
    message = cmd[1]

    recipients = cmd[1].split().pop()
    for recipient in recipients:
        if recipient[0] == '#':
            for channel in channels:
                if channel.name == recipient[1:]:
                    channel.privateMessageChannel(user, message)
        else:
            for channel in channels:
                for u in channel.users:
                    if u.nickname == recipient:
                        sendMSG(f"|Private| {user.nickname}: {message}", u)


def safePipe(user):
    try:
        return user.socket.recv(1024).decode('utf-8')
    except:
        user.socket.close()
        print(f'user {user.nickname} disconnected unexpectedly')
        for c in channels:
            for u in c.users:
                if u == user:
                    c.leave(user)
        exit()


# Command Handling
class handleClient(threading.Thread):
    def __init__(self, user):
        threading.Thread.__init__(self)
        self.user = user

    def run(self):
        global channels
        global awaitingPrivate

        self.channel = None

        sendMSG(listUserCommands(), self.user)

        while True:
            msg = safePipe(self.user)

            if "JOIN" in msg:
                join(self.user, msg)
            elif msg == "PING":
                sendMSG("PONG", user)
            elif msg == "LIST":
                for u in self.channel.users:
                    sendMSG(f'{u.nickname}\n', self.user)
            elif "PMMSG" in msg:
                pm(self.user, msg)
            elif msg == "EXIT":
                self.channel.leave(self.user)
                sendMSG("EXIT", self.user)
                self.user.socket.shutdown
                print(f'user {self.user.nickname} has disconnected')
                break
            else:
                print(msg)


connectUser(sock)
