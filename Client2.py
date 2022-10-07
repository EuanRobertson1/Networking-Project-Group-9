import socket

sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

Port = 6667
#Server ="0000:0000:0000:0000:0000:0000:0000:0001"
#SADDRESS = (Server, Port)
SADDRESS = ('localhost', Port)

print('connecting to {} port {}'.format(*SADDRESS))
sock.connect(SADDRESS)
#sock.bind(SADDRESS)

try:

    # Send messages
    message = input("Type in Chat: ").encode('utf-8')
    print('sending '.format(message))
    sock.sendall(message)

    # Look for the response
    msg_received = 0
    msg_expected = len(message)

    while msg_received < msg_expected:
        data = sock.recv(16)
        msg_received += len(data)
        print('received '.format(data))

except:
    print("nothing to see here")