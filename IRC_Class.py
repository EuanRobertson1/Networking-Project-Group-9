import socket
import sys
import time


# Group 9
# A class containing important functions for the IRC bot to work properly


class IRC_Functs:
    soc = socket.socket()  # create the socket

    def __init__(self):
        # initialise the socket
        self.soc = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

    # function for connecting to the IRC server
    def connect(self, serverAddress, portNum, chanName, nickname):
        # server connection
        self.soc.connect((serverAddress, portNum))

        # user setup
        self.soc.send(bytes("USER " + nickname + " " + nickname + " " + nickname + " :python\n",
                            "UTF-8"))  # fill in the nickname form
        self.soc.send(bytes("NICK " + nickname + "\n", "UTF-8"))

        # join a channel
        self.soc.send(bytes("JOIN " + chanName + "\n", "UTF-8"))

    # ping pong with server
    def ping(self):
        time.sleep(1)

        # get response from server
        servResp = self.soc.recv(2040).decode("UTF-8")

        if servResp.find('PING') != -1:
            self.soc.send(bytes('PONG ' + servResp.split()[1] + '\r\n', "UTF-8"))

        return servResp
