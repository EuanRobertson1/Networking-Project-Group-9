from IRC_Class import *
import os
import random

#Group 9
#bot for connecting to IRC server


serverAddress = "0000:0000:0000:0000:0000:0000:0000:0001"
portNum = 6667
chanName = "#test"
nickname = "Darius"
ircServer = IRC_Functs()


#connect using irc_class connect function
ircServer.connect(serverAddress, portNum, chanName, nickname)

#respond to pings from server
while True:
    text = ircServer.ping()
    print(text)