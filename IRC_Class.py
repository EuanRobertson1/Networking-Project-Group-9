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

        #-----user setup--------
        #format nicknames
        botNick = (bytes("NICK " + nickname + "\n", "UTF-8"))
        botUser = (bytes("USER " + nickname + " " + nickname + " " + nickname + " :python\n","UTF-8"))
        #send formatted nicknames to server
        self.soc.send(botUser) 
        self.soc.send(botNick)

        #---join a channel------
        #format the channel name
        chanToJoin = (bytes("JOIN " + chanName + "\n", "UTF-8"))
        #send formatted channel name to server
        self.soc.send(chanToJoin)

    # ping pong with server
    def ping(self):
        time.sleep(1)

        # get response from server
        servResp = self.soc.recv(2040).decode("UTF-8")

        if servResp.find('PING') != -1:
            #format the response
            botResp = (bytes('PONG ' + servResp.split()[1] + '\r\n', "UTF-8"))
            #send response to server
            self.soc.send(botResp)

        return servResp
