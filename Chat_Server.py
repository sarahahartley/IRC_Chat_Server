import socket
import select #python Library that runs OS level I/O regardless of the OS
from random import randrange #generate random nunmber
import asyncio
import sys, time



HEADER_LENGTH =1024
__timeout = 60
IP= "10.0.42.17" #Ubuntu IP
PORT= 6667
is_pong_recived=False


server_socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Configure the socket to work in IPv4, and as a tcp stream
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1) #Allows the server to still work if the port we are wanting is already in use

server_socket.bind((IP, PORT)) #Bind both the ip address with the port
server_socket.listen()  #Listen for more connections

sockets_list=[server_socket] #list of sockets that have joined the server

clients = {} #List of clients

channel_list={} #List of channels


def main():
    run_server()


output_socks = []
message_queues = {}

def run_server():
    while True:
        #Use selects funtionality
        read_sockets, write_sockets, exception_sockets = select.select(sockets_list, output_socks, sockets_list, 10)
        
        for notified_socket in read_sockets:
            #Check what socket you are dealing with
            if notified_socket == server_socket:
                #Just joined the server
                client_socket, client_address= server_socket.accept() # Join servers
                client_socket.setblocking(0)
                #add to list of sockets
                sockets_list.append(client_socket)
            else:
                #get message
                message = receive_message(notified_socket)
                #check if message is empty
                if (message == ""):
                    if notified_socket in output_socks:
                        output_socks.remove(notified_socket)
                    sockets_list.remove(notified_socket)
                    notified_socket.close()
                
                try:
                    #Set time of the last recived message
                    client = clients[notified_socket]
                    client.last_rec_message_time = time.time()
                except KeyError as ke:
                    print("client not yet in list: " + str(ke))
                    pass
                #Parse the reply from Hexchat
                lines = message.split("\r\n")

                #Loop for the whole intruction
                for x in range(len(lines)):
                    #check if line is empty
                    if (lines[x] != ""):
                        #Parse the message at every space
                        splitLine = lines[x].split(" ")
                        #Check word that was parsed
                        if (splitLine[0] == "CAP"):
                            pass
                        elif (splitLine[0] == "USER"):
                            #Check if user is already a member of the server
                            if (client_socket in clients):
                                #Change username
                                client = clients[client_socket]
                                client.set_user_stuff(splitLine[1], splitLine[2], splitLine[3], splitLine[4])
                                send_welcome_if_registered(client)
                            else:   
                                #Add the user to the server
                                clients[client_socket] = Client(client_socket, uname= splitLine[1],hname=splitLine[2],sname=splitLine[3], rname=splitLine[4])

                        elif (splitLine[0] == "JOIN"):
                            #User wants to join a channel 
                            channel_name=splitLine[1]
                            cname=channel_name[1:]

                            #Check if channels list is empty or if channel exists
                            if ((len(channel_list)==0) or cname not in channel_list):
                                #Get channel name
                                channel_name=splitLine[1]
                                cname=channel_name[1:]
                                
                                #Create new channel
                                channel = Channel(cname)
                                
                                #Add channel to list of channels
                                channel_list[cname] =channel

                            # add the user to the channel
                            try:
                                client = clients[client_socket]
                            except KeyError as error:
                                pass

                            channel_list[cname].add_user_to_channel(client)

                            #Get the nicknames of every user in a channel
                            nicks = " ".join(y.nickname for y in channel_list[cname].channel_members)

                            #Send the message to the channel
                            send_to_channel(create_user_command("JOIN " + splitLine[1], client), channel_list[cname], notified_socket, send_to_sender=True)
                            #Send message to user
                            message = (create_server_command("331 "+client.nickname +" "+ channel_name +" :No topic is set")) + \
                                (create_server_command("353 "+ client.nickname+ " = "+channel_name+" :"+ nicks)) + \
                                (create_server_command("366 "+client.nickname +" "+ channel_name +" :End of NAMES list"))
                            send_message(notified_socket, message)

                        
                        elif (splitLine[0] == "NICK"):
                            #Check if nickname is already taken
                            for c in clients.values():
                                if (splitLine[1] == c.nickname):
                                    #Nickname exists at some socket
                                    if (c.socket != notified_socket):
                                        #Nickname exists at different socket thus already in use
                                        send_message(notified_socket, create_server_command("433 * " + c.nickname + " :Nickname is already in use"))
                                        break
                            #Add a nickname
                            if (client_socket in clients):
                                client = clients[client_socket]
                                client.set_nickname(splitLine[1])
                                send_welcome_if_registered(client)
                            else:
                                clients[client_socket]= Client(client_socket, nname= splitLine[1])
                        elif (splitLine[0] == "PRIVMSG"):
                            #Send private message
                            if (splitLine[1][0] == "#"):
                                #Message is for a channel
                                channel = channel_list[cname]
                                send_to_channel(create_user_command(lines[x], clients[notified_socket]), channel, notified_socket)
                            else:
                                #Send private message to user
                                nickname = splitLine[1]
                                for i in range(len(channel.channel_members)):
                                    target = channel.channel_members[i]
                                    if (target.nickname == nickname):
                                        send_message(target.socket, create_user_command(lines[x], clients[notified_socket]))

                        elif (splitLine[0] =="WHO"):
                            #Who command
                            message1=""
                            #Get list of all members of a channel
                            for counter in range(len(channel_list[cname].channel_members)): 
                                client=channel_list[cname].channel_members[counter]
                                message1 +="352 "+client.nickname+" "+channel_name+" "+client.username+" "+client.servername +" " + \
                                    socket.gethostname() + " " + client.nickname + " H :0 "+client.realname + " "
                            #Send message to user
                            message = create_server_command(message1[:-1])
                            message += create_server_command("315 "+client.nickname +" "+ channel_name +" :End of WHO list")

                            send_message(notified_socket,message)
                        elif (splitLine[0] =="PING"):
                            #User send a ping respond with a pong
                            pong(notified_socket,splitLine[1])
                        elif (splitLine[0] =="PONG"):
                            #User responded with a pong
                            clients[notified_socket].waiting_for_pong = False
                        elif (splitLine[0] =="QUIT"):
                            #User wants to leave the server
                            disconnect_from_server(client, splitLine[1])
                        else:
                            #Input not recognised
                            print ("Sorry - error with input")
                            sys.stdout.flush()

                if message is False:
                    #Message was not recived successfully
                    #Close the connect to the socket
                    print(f"Closed connection from {clients[notified_socket]['data'].decode('utf-8')}")
                    sockets_list.remove(notified_socket)
                    del clients[notified_socket]
                    

        for notified_socket in exception_sockets:
            sockets_list.remove(notified_socket)
            del clients[notified_socket]

        #Goes here after timeout of 5 seconds in select.select
        if not len(sockets_list) or not len(read_sockets):
            ping_all()

# Method send a welcome message to user if they are a member of the server
# Params:
# client : The client object who joined the server
def send_welcome_if_registered(client):
    #Check if client is a member of the server
    if (client.is_registered()):
        #Create and send message
        message  = create_server_command("001 " + client.nickname + " :Hi, welcome to the server")
        message += create_server_command("002 " + client.nickname + " :Your host is " + socket.gethostname() + ", running version 0.1.7")
        message += create_server_command("003 " + client.nickname + " :This server was created at some point")
        message += create_server_command("004 " + client.nickname + " " + socket.gethostname() + "our_sercer-0.1.7 o o")
        message += create_server_command("005 " + client.nickname + " -nothing :are supported by this server")
        message += create_server_command("422 " + client.nickname + " :MOTD File is missing")
        send_message(client.socket, message)
    
    
# Method send a welcome message to user if they are a member of the server
# Params:
# message : Message the user wants to send
# channel : Destination channel
# sender_socket : socket of the message sender
# send_to_sender : Boolean 
def send_to_channel(message, channel, sender_socket, send_to_sender = False):
    for i in range(len(channel.channel_members)):
        client = channel.channel_members[i]
        if (send_to_sender or client.socket != sender_socket):
            send_message(client.socket, message)

# Method reply to a ping command
# Params:
# sock : socket to which the pong is sent to
# rec_nonce : Nonce that was recived from the ping to send back
def pong(sock,rec_nonce):
    #Send message back with the nonce
    send_message(sock, create_server_command("PONG " + socket.gethostname() + " :" + rec_nonce))


# Method leave the server
# Params:
# user : client Object that is leaving the server
# leave_message : Message to send when the lient object leaves the server
def disconnect_from_server(user, leave_message = ":Leaving"):

    #remove user from from all the channels they are connected to
    for channel in channel_list.values():
        try:
            
            #Check if user is in any channels
            if (user in channel.channel_members):
                #Leave channel
                send_to_channel(create_user_command("QUIT " + leave_message , user), channel, user.socket, False)
            channel.channel_members.remove(user)

            print("removed: " + user.nickname)
        except Exception as e:
            print("could not remove: " + str(e))
    
    try:
        #remove from client dictionary
        del clients[user.socket]
    except KeyError as keyexpt:
        print("The user you are trying to delete "+ str(keyexpt)+ " does not exist")
        pass
    except Exception as e:
        print("could not delete: "  + str(e))
        pass

    try:
        #remove from list of sockets
        global sockets_list
        sockets_list.remove(user.socket)
        user.socket.close()
    except Exception as e:
        print("Failed to remove socket: " + str(e))
            


# Method to recive a message
# Params:
# client_socket : socket of the user reciving the message
# leave_message : Message to send when the client object leaves the server
def receive_message(client_socket):
    try:
        full_Message = client_socket.recv(HEADER_LENGTH) #Get the message
        if not len(full_Message):
            return ""

        #Print Acknowledgement
        print (str(client_socket.getpeername()),"Received:", full_Message)
        return full_Message.decode('utf-8')

    except Exception as e:
        print(str(e))
        return ""

# Method to send a message
# Params:
# socket : socket of the user reciving the message
# message : Message to send
def send_message(socket, message):
    try:
        #Send message t the socket
        print(str(socket.getpeername()), "Sending: ", str(message))
        if type(message) is str:
            message = message.encode("utf-8")
        socket.send(message)
    except OSError as ose:
        print("Failed to send message: " + str(ose))

# Method to create a message in the right format to be sent from the server
# Params:
# message : Message to send
def create_server_command(message):
    return (":" + socket.gethostname() + " " + message + "\r\n").encode("utf-8")

# Method to create a message in the right format to be sent from a user
# Params:
# message : Message to send
# client : Client object
def create_user_command(message, client):
    prefix = client.nickname + "!" + client.username + "@" + client.servername
    return (":" + prefix + " " + message + "\r\n").encode("utf-8")

# Method to send a ping
# Params:
# client : Client object
def ping(client):
    client.waiting_for_pong=True
    #Generate random number
    randomNum = randrange(9999999999)
    #Send random number as a ping command
    send_message(client.socket, "PING " + str(randomNum) + "\r\n")

# Method to send a ping to all users
def ping_all():
    #Loop thorugh all the client objects
    for client in list(clients.values()):
        play_sports(client)


# Method to check if client is alive with pings and pongs
# Params:
# client: Client object that is being checked
def play_sports(client):
    now = time.time()
    if (now > client.last_rec_message_time + (__timeout/2)) and not client.waiting_for_pong:
        # more than halfway to timeout (and ping not sent yet) -> send a ping
        ping(client)
    elif (now > client.last_rec_message_time + __timeout):
        #timeout has passed -> disconnect
        disconnect_from_server(client)
        pass
    else:
        #haven't timed out
        pass
        


class Channel():
    #initializing the variables
    channel_name = ""
    channel_members= []

    #defining constructor
    def __init__(self,channelname):
        self.channel_name = channelname

    # Method to add a user to the channel
    # Params:
    # self: self refering object
    # client:  Client object that will be added to the channel
    def add_user_to_channel(self,client):
        self.channel_members.append(client)


class Client():
    #defining constructor
    def __init__(self, socket, nname=None, uname = None, hname = None,sname =None, rname = None):
        self.nickname=nname
        self.realname=rname
        self.servername=sname
        self.username = uname
        self.hostname= hname
        self.socket = socket
        self.waiting_for_pong = False
        self.last_rec_message_time = time.time()

    # Method to check if a user is registed to the server 
    # Params:
    # self: self refering object
    def is_registered(self):
        #true if both nickname and username set
        return self.nickname != None and self.username != None


    # Method to get value of nickname
    # Params:
    # self: self refering object
    def get_nickname(self):
        return self.nickname

    # Method to set value of nickname
    # Params:
    # self: self refering object
    # newnickname: Users new nickname
    def set_nickname(self, newnickname):
        self.nickname = newnickname

    #Set getters and setters for variable
    Nickname = property(get_nickname, set_nickname)
   
    # Method to get value of nickname
    # Params:
    # self: self refering object
    def get_realname(self):
        return self.realname

    # Method to set value of nickname
    # Params:
    # self: self refering object
    # newrealname: Users new real name
    def set_realname(self, newrealname):
        self.realname = newrealname

    # Method to set value of a user
    # Params:
    # self: self refering object
    # uname: user name
    # hname: host name
    # sname: server name
    # rname: real name
    def set_user_stuff(self, uname, hname, sname, rname):
        self.realname=rname
        self.servername=sname 
        self.username = uname
        self.hostname= hname

    #Set getters and setters for variable
    Realname = property(get_realname, set_realname)

    # Method to get value of nickname
    # Params:
    # self: self refering object
    def get_servername(self):
        return self.servername

    # Method to set value of nickname
    # Params:
    # self: self refering object
    def set_servername(self, newservername):
        self.servername = newservername
    
    #Set getters and setters for variable
    Servername = property(get_servername, set_servername)




#Call main function
if __name__ == '__main__':
    main()
