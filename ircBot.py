from ast import parse
from IRC_Class import *
import os
import random
import optparse



#Group 9
#bot for connecting to IRC server

#create CL arguments parser
parser = optparse.OptionParser()

#add some options
parser.add_option("--a", "--address", dest="address", help="The IPV6 address of the IRC server you want the bot to connect to")
parser.add_option("--c", "--channelName", dest="channelName", help="The name of the channel you want the bot to join")
parser.add_option("--n", "--nickname",dest="nickname", help="The nickname you want the bot to have in the IRC server")

(options, arguments) = parser.parse_args()

#flag error(s) if no arguments
if not options.address:
    parser.error("missing arguments! (try --h if stuck)")

if not options.channelName:
    parser.error("missing arguments! (try --h if stuck)")

if not options.nickname:
    parser.error("missing arguments! (try --h if stuck)")

#get variable values from CL arguments
serverAddress = options.address
portNum = 6667
chanName = options.channelName
nickname = options.nickname
ircServer = IRC_Functs()


#connect using irc_class connect function
ircServer.connect(serverAddress, portNum, chanName, nickname)

#respond to messages from server
while True:
    text = ircServer.messages(chanName, nickname)
    print(text)