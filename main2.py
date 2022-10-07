import socket
import threading

Port = 6667
#Server ="0000:0000:0000:0000:0000:0000:0000:0001"
#ADDRESS = (Server, Port)
ADDRESS = ('localhost', Port)
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

print('Server Starting on {} port {}'.format(*ADDRESS))
sock.bind(ADDRESS)

#channel
class Channel:

    #initialise object attributes
    def __init__(self, name):
        self.name = name
        self.users = []

    #add client to list
    def join(self, user):
        self.users.append(user)
        for u in self.users:
            sendMSG(f'user {user.nickname} has joined the chat', u)

    #remove client
    def leave(self, user):
        self.users.remove(user)
        for u in self.users:
            sendMSG(f'user {user.nickname} has left the channel', u)

    #more messages

    def privateMessageChannel(self, user, data):
        if data == "":
            return
        m = f"|private| {user.nickname}: {data}"

#create channel
class User:
    def __init__(self, socket, addr, username, nickname, realname):
        self.socket = socket
        self.address = addr
        self.username = username
        self.nickname = nickname
        self.realname = realname

channels = [Channel("Test"), Channel("Unicorn")]

# Listen for messages
sock.listen(1)
print('waiting for a connection')

while True:

    try:
        connection, client_address = sock.accept()

    except:
        print('Error')

        # Receive Messages
        while True:
            data = connection.recv(16)
            print('received {!r}'.format(data))

            if data:
                connection.sendall(data)
            else:
                print('no data from', client_address)

            username = ""
            nickname = ""
            realname = ""

            while True:

                msg = socket.recv(1024).decode('utf-8')

                if "USER" not in msg:
                    socket.send("please enter a correct USER command".encode('utf-8'))
                    continue

                for c in channels:
                    for u in c.users:
                        if u.username == username:
                            socket.send(f'sorry username already taken: {username} '.encode('utf-8'))
                            continue

            cmd = msg.split()

            username = cmd[1]
            realname = cmd[4]

            while True:

                if "NICK" not in msg:
                    socket.send("please enter a correct NICK command".encode('utf-8'))
                    continue

                cmd = msg.split()
                nickname = cmd[1]

                break

        user = User(socket, ADDRESS, username, nickname, realname)

    sendMSG(f'welcome to the server {user.nickname}!\n', user)

thread = handleClient(user)
thread.start()

#Client Commands
def listUserCommands():
    msg = "Commands"
    msg = msg + "\nJOIN - Join a Channel"
    msg = msg + "\nPING - PING PONG"
    msg = msg + "\nPMMSG - private message to a Client"
    msg = msg + "\nEXIT - you exit\n"
    return msg

#send messages
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

#join a channel
def join(user, msg):
    chanName = msg.strip().split()[1][1:]

    print(chanName)

    channel = None

    for c in channels:
        if c.name == chanName:
            channel = c

    if channel == None:
        data("\nPlease enter a valid channel name", user)
        return

    for c in channels:
        for u in c.users:
            if u == user:
                c.leave(user)

    channel.join(user)
    print(f'user {user.nickname} has has joined channel {channel.name}')


#private messages handling
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
                        data(f"|Private| {user.nickname}: {message}", u)


#Command Handling
class handleClient(threading.Thread):
    def __init__(self, user):
        threading.Thread.__init__(self)
        self.user = user

    def run(self):
        global channels
        global awaitingPrivate

        self.channel = None

        data(listUserCommands(), self.user)

        while True:

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
                self.channel.messageChannel(self.user, msg)
