# Networking Project Group 9

##Background
We were required to make a basic IPv6 IRC bot and Server part of the Dundee University 3rd year Computing Networks module (AC31008). 
THe main contributors of this Project were:
Euan Robertson - 2463967@dundee.ac.uk
Matthew Gallacher - 2436912@dundee.ac.uk
Georghios Tziouliou - 2412649@dundee.ac.uk
Antonis Tziouliou - a,tziouliou@dundee.ac.uk

######Files
main2.py is the finished Server file
ircBot.py is the finished bot file which uses functions from the IRC_Class.py
test.py and Server.py contain code from @jrosdahl's [miniircd project](https://github.com/jrosdahl/miniircd) which we used for testing purposes. 

##bot usage
Running the bot requires the use of a few arguments:
--a to specify the IPV6 address
--c to specify a channel that the bot should join
--n to specify a nickname for the bot

Once connected to the sever the bot will respond to a few commands issued by other users in the channel:
!help will make the bot explain its purpose in a message sent to the channel
!hello will make the bot say hello
!slap will make the bot slap a random user in the channel *this is slighty buggy and needs fixing*
/msg *bot nickname* will make the bot send the user a dm with a random fact
!leave will make the bot leave the channel
