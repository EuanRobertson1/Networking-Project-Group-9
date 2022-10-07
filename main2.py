import socket
import threading

Port = 6667
#Server ="0000:0000:0000:0000:0000:0000:0000:0001"
#ADDRESS = (Server, Port)
ADDRESS = ('localhost', Port)
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

print('Server Starting on {} port {}'.format(*ADDRESS))
sock.bind(ADDRESS)

# Listen for messages
sock.listen(1)

while True:

    print('waiting for a connection')
    connection, client_address = sock.accept()
    try:

        # Receive Messages
        while True:
            data = connection.recv(16)
            print('received {!r}'.format(data))

            if data:
                connection.sendall(data)
            else:
                print('no data from', client_address)
                break

    finally:

    #not Done
            class ChannelThread(threading.Thread):
                def __init__(self):
                 threading.Thread.__init__(self)

            def run(self):
                while True:
                    new_client = self.chan_sock.accept()

                    def sendall(self, msg):
                        for client in self.clients:
                            client[0].sendall(msg)

                    class Channel(threading.Thread):
                        def __init__(self):
                            threading.Thread.__init__(self)

                    self.daemon = True
                    self.channel_thread = ChannelThread()


                    def public_address(self):
                        return "tcp://%s:%d" % (socket.gethostname(), self.channel_thread.port)

                    def register(self, channel_address, update_callback):
                        host, s_port = channel_address.split("//")[-1].split(":")


                    port = int(Port)
                    self.peer_chan_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.peer_chan_sock.connect((ADDRESS))
                    self.start()

                    def deal_with_message(self, msg):
                        self._callback(msg)

                    def run(self):
                        data = ""

                    while True:
                        new_data = self.peer_chan_sock.recv(1024)

                def send_value(self, channel_value):
                        self.channel_thread.sendall("%s\n\n" % channel_value)

         # Clean up
            print("Done, waiting for next message")