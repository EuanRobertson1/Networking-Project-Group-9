from IRC_Class import *
import os
import random

#bot for connecting to IRC server

serverAddress = "127.0.0.1"
portNum = 6667
chanName = "#test"
nickname = "Darius"
ircServer = IRC_Functs()
#nicknamePass = "test"
#botPass = "<%= @test_password %>"

#connect using irc_class connect function
ircServer.connect(serverAddress, portNum, chanName, nickname)

#respond to pings from server
while True:
    text = ircServer.ping()
    print(text)