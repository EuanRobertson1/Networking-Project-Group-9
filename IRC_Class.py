from cgitb import text
from http import server
import socket
import sys
import time
import re


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

    #Function that allows bot to respond to messages
    def messages(self, channel,nickname):
        time.sleep(1)

        # get response from server
        servResp = self.soc.recv(2040).decode("UTF-8")

        if servResp.find('PING') != -1:
            #format the response
            botResp = (bytes('PONG ' + servResp.split()[1] + '\r\n', "UTF-8"))
            #send response to server
            self.soc.send(botResp)

        #source used when working out how to respond to messages - https://unix.stackexchange.com/questions/710423/facing-difficulties-sending-bytes-containing-white-spaces-python-irc-bot
        if servResp.find('!hello')!= -1:
            
            #format response 
            botResp = (bytes('PRIVMSG ' + channel + " " + ":Hello " + '\n', "UTF-8" ))
            #send response to server
            self.soc.send(botResp)
        
        if servResp.find('!slap')!= -1:
            #format response
            botResp = (bytes('PRIVMSG ' + channel + " " + ":Ouch! That hurt :( " + '\n', "UTF-8" ))
            #send response to server
            self.soc.send(botResp)
        
        #Bot responding to /msg. Worked out with help of this source - https://stackoverflow.com/questions/40076143/python-irc-bot-distinguish-from-channel-messages-and-private-messages
        if servResp.find('PRIVMSG ' )!= -1:
            #check if message is meant for bot or whole channel
            splitResp = servResp.split()
            #get username of sender
            userNick = splitResp[0]
            sep = '!'
            nickSep = userNick.split(sep, 1)[0] 
            #only respond if message was sent directly to bot
            if splitResp[2] == nickname:
                
                #format response
                botResp = (bytes('PRIVMSG ' + nickSep + " :" + "Noxus Will Rise!" + '\n', "UTF-8"))
                #send response to server
                self.soc.send(botResp)

        #to make bot leave (testing puposes)
        if servResp.find('!leave')!= -1:
            quit()

        return servResp
