import socket
import select
import errno #map error codes
import sys
from datetime import datetime
from random import randrange
import random

HEADER_LENGTH= 1024

IP= "10.0.42.17" #Ubuntu IP
PORT= 6667

my_username= "ProBot"
botNick = "ProBot"
botRealName = "realname"
channel = "test"

client_socket= None


def init():
    # usage: py chat_bot.py [serverIP] [port] [channel] [botname] [botnickname]
    if len(sys.argv) >= 3:
        global IP, PORT, channel, my_username, botNick
        IP = sys.argv[1] #set the IP address to command line variable 1
        PORT = int(sys.argv[2]) #set the IP address to command line variable 2
        if len(sys.argv) >= 4:
            channel = sys.argv[3] #set the channel name to command line variable 3
            if len(sys.argv) == 5:
                my_username = sys.argv[4] #set the username to command line variable 4
                botNick = sys.argv[4] #set the nickname to command line variable 5
    

#Method to connect to the server
def connect():
    global client_socket
    client_socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Configure the socket to work in IPv4, and as a tcp stream
    client_socket.connect((IP, PORT)) # Connect to server
    client_socket.setblocking(False) # Receive functionality wont be blocking

    # USER <username> <hostname> <servername> :<realname>
    message = "USER " + \
      my_username + " " + \
      socket.gethostbyname(socket.gethostname()) + " " + \
      IP + " " + \
      ":" + botRealName
    send_command(message) #Send USER command

    # NICK <nickname>
    message = "NICK " + botNick
    send_command(message) #Send NICK command


#Method to send the JOIN command
def join_channel():
    send_command("JOIN #" + channel) #Send JOIN command


# Main method
def main():
    init()
    connect()
    join_channel()
    welcomeMessage = "Hello! My name is ServerBot. If you want to talk to me type '!' before your phrase."
    send_message(welcomeMessage)
    receive_message()


# Method to reply to a private message
# Params:
# message : The message
# destination : The nickname of the user who sent the message
def send_message(message, destination = None):
    if (destination == None): 
        destination = "#" + channel
    if (message != ""): #If message is not blank	
        message= ("PRIVMSG " + destination + \
          " :" + message + "\r\n")	
        print("sending: " + message)
        message = message.encode("utf-8")
        client_socket.send(message) #send message


# Method to send a message, and append \r\n to the end
def send_command(message):   
    if (message != ""): #If message is not blank	
        send_command_noLn(message + "\r\n") #Add \r\n to the end of the message


# Method to send a message
def send_command_noLn(message):  
    if (message != ""): #If message is not blank		
        print("sending: " + message)
        message = (message).encode("utf-8")
        client_socket.send(message)  #send message
        

# Method to send reply to ping message
# Params: 
# rec_nonce : the nonce sent with the PING
def pong(rec_nonce):
    send_command_noLn("PONG " + rec_nonce) #reply to the PING 


# Method to recieve a message from the client socket
def receive_message():
    while True:
        try:
            message = client_socket.recv(1024) #recieve a message from the client socket

            #Handles if there was no message
            if not len(message):
                print("Connection closed by the server")
                sys.exit()

            message = message.decode("utf-8") #decode the message

            print(f"received: {message}")
            parse_message(message) #split up the message

        except IOError as e: #catch IOerror
            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                print('Reading error', str(e))
                sys.exit()
            continue

        except Exception as e: #catch error
            print('General error',str(e))
            sys.exit()


# Method to parse a private message 
# Params:
# message : the message to parse
# sender : the nickname of the client who sent the message
def parse_private_msg(message, sender):
    try:
        myFile = open(r"funFacts.txt","r", encoding="utf8") #open the fun facts text file
        lines = myFile.readlines() #read in each line
        reply = (random.choice(lines)) #choose a random fun fact to reply

    except IOError: #catch IOerror
        reply = "Unfortunately I don't know any fun facts at the moment :("

    except Exception as e: #catch error
        reply = "Something went wrong remembering fun facts, sorry. (" + str(e)+ ")"

    send_message(reply, sender) #send message


# Method to parse a channel message
# Params: 
# message : the message to parse
def parse_channel_msg(message):
    message = message.split("\r\n", 1)[0] # get rid of the trailing \r\n

    if (message == "!day"):
        print("\n-------get date-------")
        date = datetime.now() #get the current date and time
        current_date = date.strftime("%d.%m.%Y") #format the date
        reply = "Todays date is: " + current_date

    elif (message == "!time"):
        print("\n-------get time-------")
        time = datetime.now() #get the current date and time
        current_time = time.strftime("%H:%M") #format the time
        reply = "The time is: " + current_time

    elif (message[0] == "!"):
        reply = "Unrecognized command: " + message 

    else:
        reply = "error"
        return

    send_message(reply) #send response


# Method to parse the message recieved from the client socket
def parse_message(message):
    lines = message.split("\r\n") #split each line
    for line in lines: #handle each line
        if (line): #if line is not blank
            splitMessage = line.split(" ") #split the line into words

            if (splitMessage[0] == "PING"):
                pong(splitMessage[1]) #reply with pong

            elif (splitMessage[1] == "433"): #Username already taken
                message = "NICK " + str(randrange(99)) + botNick #generating a new nickname by appending a random number from 0-99
                print("nick taken, trying " + message)
                send_command(message) #send new nickname

            elif (splitMessage[0][0] == ':'):
                colonSplitMsg = line.split(':', 2)
                msgUserNick = colonSplitMsg[1].split('!', 1)[0] # get nickname

                if (splitMessage[1] == "PRIVMSG"): #private message
                    if (splitMessage[2] == botNick):
                        parse_private_msg(colonSplitMsg[2], msgUserNick)

                    elif (splitMessage[2] == "#" + channel): #channel message
                        parse_channel_msg(colonSplitMsg[2])


if __name__ == '__main__':
    main()
