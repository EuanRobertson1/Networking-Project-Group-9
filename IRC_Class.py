from cgitb import text
from http import server
import socket
import sys
import time
import re
from datetime import date, datetime
import randfacts
import random


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
    #Source used when working out how to respond to messages - https://unix.stackexchange.com/questions/710423/facing-difficulties-sending-bytes-containing-white-spaces-python-irc-bot
    def messages(self, channel,nickname):
        time.sleep(1)

        # get response from server
        servResp = self.soc.recv(2040).decode("UTF-8")

        #split response into list (used when checking who sent message or which channel or user message is intended for)
        splitResp = servResp.split() 

        #get username of sender
        nickSep = self.getSender(splitResp)
        
        
        #Respond to server pings
        if servResp.find('PING') != -1:
            #format the response
            botResp = (bytes('PONG ' + servResp.split()[1] + '\r\n', "UTF-8"))

            #send response to server
            self.soc.send(botResp)

        #say hello to message sender and state current date and time
        if servResp.find('!hello')!= -1:
            #format date & time
            currentDate = datetime.now()
            d = currentDate.strftime("It is currently %H:%M and the date is %d-%m-%Y")

            #format response 
            botResp = (bytes('PRIVMSG ' + channel + " " + ":Hello " + nickSep + ", " + d + '\n', "UTF-8" ))

            #send response to server
            self.soc.send(botResp)
        
        #allows message sender to trout slap a random other user in the channel
        #Partially broken as list contains domain name 
        if servResp.find('!slap')!= -1:
            #get names of users in channel
            allNicks = self.getAllNicknames(channel)

            #choose a random user from the list
            chosenUser = random.choice(allNicks)

            #modfiy if slapping self
            if chosenUser == nickSep:
                chosenUser = "themself"

            #format response
            botResp = (bytes('PRIVMSG ' + channel + " :" + nickSep + " slaps "  + chosenUser + " with a large trout" '\n', "UTF-8" ))

            #send response to server
            self.soc.send(botResp)
        
        #Bot responding to /msg. Worked out with help of this source - https://stackoverflow.com/questions/40076143/python-irc-bot-distinguish-from-channel-messages-and-private-messages
        if servResp.find('PRIVMSG ' )!= -1:
            
             
            #only respond if message was sent directly to bot and not to a channel i.e. check if index of list where the target channel/user is stored matches the nickname of the bot
            if splitResp[2] == nickname:
                
                #get a random fact from the 'randfacts' library
                fact = randfacts.get_fact()

                #format response
                botResp = (bytes('PRIVMSG ' + nickSep + " :" + fact + '\n', "UTF-8")) 

                #send response to server
                self.soc.send(botResp)

        #to make bot leave (testing puposes)
        if servResp.find('!leave')!= -1:
            quit()
        return servResp


    #function that uses the list version of the server response to return the nickname of the message sender
    def getSender(self,splitResp):
        
        #modify the list to only contain the nickname of the message sender
        userNick = splitResp[0].strip(':')#remove colon at start

        sep = '!'#specify which character to remove text after

        nickSep = userNick.split(sep, 1)[0]#remove uneccessary bits after the specified character
        
        #return variable containing only nickname of the message sender
        return nickSep


    #function that returns a list of all users in channel
    def getAllNicknames(self,channel):
        #send /names to server
        botResp = (bytes('NAMES ' + channel + '\n', "UTF-8"))
        self.soc.send(botResp)

        #get server response
        servResp = self.soc.recv(2040).decode("UTF-8")

        #remove all the unnecessary string/characters and make into a list
        s = servResp.replace(":", " ")
        s2 = s.split(r'=')[-1]
        s3 = s2.replace("#test", " ")
        s4 = s3.replace("End of NAMES list", " ")
        s5 = s4.replace("366", " ")
        nickList = s5.split()

        #return the list of users
        return nickList
         

    
        
        

        
