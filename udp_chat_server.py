# -*- coding: utf-8 -*-
from twisted.internet.protocol import DatagramProtocol
from c2w.main.lossy_transport import LossyTransport
import logging
import struct
import ctypes
from c2w.main.constants import ROOM_IDS
from c2w.main.user import c2wUser
from c2w.main.user import c2wUserStore
from c2w.main.server_proxy import c2wServerProxy
from c2w.main.movie import c2wMovieStore
from c2w.main.client_model import  c2wClientModel
from twisted.internet import reactor
logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_server_protocol')


class c2wUdpChatServerProtocol(DatagramProtocol):
    def __init__(self, serverProxy, lossPr):

        self.serverProxy = serverProxy
        self.lossPr = lossPr
        self.seq_num ={}
        self.ack_numRecu={}
        self.ack_numAenvoye={}
        self.typeMsgRecievedPrecedant={}
        self.typeMsgSentPrecedant={}
        self.clientModel=c2wClientModel()
        self.nbConnectedUser=0 
        self.ack_bit={}
        self.nbenvoi={}
#*****************************Start Protocole*****************************
    def startProtocol(self):

        self.transport = LossyTransport(self.transport, self.lossPr)
        DatagramProtocol.transport = self.transport





#*************************Reception datagram******************************

    def datagramReceived(self, datagram, (host, port)):

               
        LengthDatagram=struct.unpack_from('>LH',datagram)[1]
        LengthData=LengthDatagram-6
        msg_recu=struct.unpack_from(">LH"+str(LengthData)+"s",datagram)
        header=msg_recu[0]
        data=msg_recu[2]
        typeMsg=header>>28
        user=self.serverProxy.getUserByAddress((host, port))
        print "le type de msg est: "
        print typeMsg
        if (user==None):
            print "le user vient de se connecter"
            ack_numAenvoye=0
            ack_numRecu=header>>13 & 8191
        else:
            self.ack_numAenvoye[user.userName]=header & 8191
            self.ack_numRecu[user.userName]=header>>13 & 8191
            print "ACK num recu est: "
            print  self.ack_numRecu[user.userName]
          
		
 #+++++++++++++++++++++++++ TypeMsg=1(loginrequest)+++++++++++++++++++++++++
		
		
        if(typeMsg==1):
            
            if ((self.serverProxy.userExists(data)==True)|(len(self.serverProxy.getUserList())==8192)|(len(data)>128)):
                errorCode=1
                typeMsg=0
                ack=1
                res=0
                buf= ctypes.create_string_buffer(7)
                seq_num=0
                header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_numAenvoye<<13)|(seq_num)
                struct.pack_into('>LHB', buf,0,header,7,errorCode)
                self.transport.write(buf.raw,(host, port))
                
            else :
                if(user==None): #le user se connecte pour la 1ère fois 
                    typeMsg=14
                    ack=1
                    res=0
                    userId=self.serverProxy.addUser(data,ROOM_IDS.MAIN_ROOM,None,(host, port)) #création de l'Id du nouveau user
                    user=self.serverProxy.getUserById(userId) #récupération du user à travers son Id
                    self.seq_num[user.userName]=0   #initialisation du seq_num du user à 0
                    buf= ctypes.create_string_buffer(8)
                    header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_numAenvoye<<13)|(self.seq_num[user.userName])
                    struct.pack_into('>LHH', buf,0,header,8,userId)
                    self.EnvoiMsg(buf,user.userAddress,user.userName)
                    if(self.nbConnectedUser>0):
                        print "on envoie l'update de la liste de users aux autres qui sont dans le main room"
                        userList=self.serverProxy.getUserList()
                        for u in userList:
                            if (u.userName is not user.userName):
                                self.sendlistUserMainRoom()
                                self.seq_num[user.userName]-=1
                    self.nbConnectedUser+=1
                    self.typeMsgRecievedPrecedant[user.userName]="1"  
                    self.typeMsgSentPrecedant[user.userName]="14"    
                    
 #+++++++++++++++++++++++++++TypeMsg=15(ACK)+++++++++++++++++++++++++++++++++++++++++	                               
        if(typeMsg==15):
            print("on reçoit ACK de")
            print user.userName
            print "on compare ack_numrecu et seq_num -1 : le 1er est l'ACK num recu"
            print self.ack_numRecu[user.userName]
            print self.seq_num[user.userName]
            if (self.ack_numRecu[user.userName]== (self.seq_num[user.userName]-1)):
                print"***************num ACK correct**********"
                if (self.typeMsgRecievedPrecedant[user.userName]=="1" and self.typeMsgSentPrecedant[user.userName]=="14"):
                    print"**********Envoie de Userlist********"
                    self.sendlistUserMainRoom()
                    self.typeMsgRecievedPrecedant[user.userName]="15"
                    self.typeMsgSentPrecedant[user.userName]="2"
                    print"**********Envoie de Userlist termine********"
                elif (self.typeMsgRecievedPrecedant[user.userName]=="15" and self.typeMsgSentPrecedant[user.userName]=="2"):
                    print"******Envoi listMovie*****************"
                    self.sendlistMovie(user.userAddress,0,self.seq_num[user.userName],user.userName)
                    self.typeMsgRecievedPrecedant[user.userName]="15"
                    self.typeMsgSentPrecedant[user.userName]="3"
					
#+++++++++++++++++++++++++++TypeMsg=4(EnvoieMsgPubliqueListeUser)+++++++++++++++++++++++++++++++++++++++++
        if(typeMsg==4):
            user=self.serverProxy.getUserByAddress((host, port))
            if (user.userChatRoom==ROOM_IDS.MAIN_ROOM):
				self.envoiPublicMsgMainRoom(datagram,LengthDatagram)
            else:
				self.envoiPublicMsgMovieRoom(datagram,LengthDatagram)
			
              
#+++++++++++++++++++++++++++TypeMsg=6(RequestJoinMovieRoom)+++++++++++++++++++++++++++
        if(typeMsg==6):
            user=self.serverProxy.getUserByAddress((host, port))
            print"le serveur comprend le msg on y est "
            self.envoiAck(self.ack_numAenvoye[user.userName],user.userAddress)
            userId=struct.unpack_from(">H",datagram,6)[0]
            movieTitle=self.definitionRoomName(datagram)
            print movieTitle
            #user=self.serverProxy.getUserById(userId)
            user.userChatRoom=movieTitle
            self.serverProxy.startStreamingMovie(movieTitle)
            self.sendlistUserMainRoom()
            self.sendlistUserMovieRoom(movieTitle)
#+++++++++++++++++++++++++++TypeMsg=7(RequestJoinMainRoom)+++++++++++++++++++++++++++               

        if(typeMsg==7):
            user=self.serverProxy.getUserByAddress((host, port))
            self.envoiAck(self.ack_numAenvoye[user.userName],user.userAddress)
            userId=struct.unpack_from(">H",datagram,6)[0]
            user=self.serverProxy.getUserById(userId)
            MovieRoomNameToLeave=user.userChatRoom
            self.serverProxy.stopStreamingMovie(user.userChatRoom)# a voir si ceci influe sur les autres qui regardent le mm filme
            user.userChatRoom=ROOM_IDS.MAIN_ROOM
            self.sendlistUserMainRoom()
            self.sendlistUserMovieRoom(MovieRoomNameToLeave)
#+++++++++++++++++++++++++++TypeMsg=8(RequestLeaveSystem)+++++++++++++++++++++++++++
        if(typeMsg==8):
            userId=struct.unpack_from(">H",datagram,6)[0]
            user=self.serverProxy.getUserById(userId)
            print "demande de deconnexion recue"
            self.envoiAck(self.ack_numAenvoye[user.userName],user.userAddress)
            print user.userName
            self.serverProxy.removeUser(user.userName)
            listUserMainRoom=self.serverProxy.getUserList()
            print listUserMainRoom 
            for u in listUserMainRoom:
                self.sendlistUserMainRoom()

#*********************************************************************************************************************************			
#			                                Useful Function
#			
#********************************************************************************************************************************

#**********************************fonction ConstrucrtionListUser**************************************************

    def constructionListeUser(self,(host, port),userName,Movie=None):
        typeMsg=2
        ack=0
        res=0
        ROO=0
        ack_num=0
        userList=self.serverProxy.getUserList()   #récupération de la liste des users du système
        userListToSend=[]
        Data_length=0
        if (Movie!=None):
	        for user in userList:
		        if (user.userChatRoom==Movie):
			        userListToSend.append(user)
			        Data_length+= len(user.userName)+3
        else:
	        for user in userList:
		        userListToSend.append(user)
		        Data_length+= len(user.userName)+3
        nb_user=len(userListToSend)
        Msg_length=Data_length+8
        buf = ctypes.create_string_buffer(Msg_length)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num[userName])
        header_data=(Msg_length<<16)|(ROO<<14)|(nb_user)
        struct.pack_into('>LL', buf,0,header,header_data) # insertion des 2 entetes
        pos_buffer=8
        for user in userListToSend:
            if (user.userChatRoom==ROOM_IDS.MAIN_ROOM):
                status=1
            else:
                status=0
            data_long_dispo=(len(user.userName)<<1)|status
            FormatData = '>BH' + str(len(user.userName)) + 's'
            struct.pack_into(FormatData,buf,pos_buffer,data_long_dispo,user.userId,user.userName)
            pos_buffer+=(len(user.userName)+3)
        self.EnvoiMsg(buf,(host, port),userName)		

#********************************** Envoi liste Utilisateur In the Main Room***********************	
    def sendlistUserMainRoom(self):

        userList=self.serverProxy.getUserList()
        for user in userList:
			if user.userChatRoom==ROOM_IDS.MAIN_ROOM:
				self.constructionListeUser(user.userAddress,user.userName)


#****************************Envoi liste Utilisateur in a Movie room***********************


    def sendlistUserMovieRoom(self,MovieRoomName):
	
        userList=self.serverProxy.getUserList()
        for user in userList:
            if (user.userChatRoom==MovieRoomName):
                print"ils sont dans la mem room"
                self.constructionListeUser(user.userAddress,user.userName,MovieRoomName)

#**********************Envoie Liste Movies*******************************************
    def sendlistMovie(self,(host, port),ack_num,seq_num,userName):

        typeMsg=3
        ack=0
        res=0
        Data_length = 0
        List_Movies=self.serverProxy.getMovieList()
        Nb_Movies=len(List_Movies)
        for movie in List_Movies: 
	        Data_length += len(movie.movieTitle)+7
        Msg_length=Data_length+8	
        buf = ctypes.create_string_buffer(Msg_length) 
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(seq_num)
        struct.pack_into('>LHH',buf,0,header,Msg_length,Nb_Movies) # Header packing
        pos_buffer=8
        for movie in List_Movies:
            Tab=movie.movieIpAddress.split('.')
            print Tab
            print("%s"%movie.movieIpAddress)
            FormatData='>BBBBHB' + str(len(movie.movieTitle)) + 's' 
            struct.pack_into(FormatData,buf,pos_buffer,int(Tab[0]),int(Tab[1]),int(Tab[2]),int(Tab[3]),movie.moviePort,len(movie.movieTitle),movie.movieTitle)# packing each movie
            pos_buffer+=len(movie.movieTitle)+7
        self.EnvoiMsg(buf,(host, port),userName)
		
#*********************Fonction envoie Public MessageMainRoom**********************************
    def envoiPublicMsgMainRoom(self,datagram,LengthDatagram):
        userId=struct.unpack_from(">LHH",datagram)[2]
        longdata=LengthDatagram-14
        message=struct.unpack_from(">"+str(longdata)+"s",datagram,14)[0]
        ack_num=0
        res=0
        ack=0
        typemsg=4
        user=self.serverProxy.getUserById(userId)
        self.envoiAck(self.ack_numAenvoye[user.userName],user.userAddress)
        userList=self.serverProxy.getUserList()
        for u in userList:
            if (u.userChatRoom == ROOM_IDS.MAIN_ROOM) and ( u.userId!=userId):
                buf= ctypes.create_string_buffer(LengthDatagram)
                header=(typemsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num[u.userName])
                formatMsg=">LHHLH"+str(longdata)+"s"
                struct.pack_into(formatMsg, buf,0,header,LengthDatagram,userId,0,0,message)
                self.EnvoiMsg(buf,u.userAddress,u.userName)

#*********************Fonction envoie Public MessageMovieRoom**********************************
    def envoiPublicMsgMovieRoom(self,datagram,LengthDatagram):
        userId=struct.unpack_from(">LHH",datagram)[2]
        longdata=LengthDatagram-14
        message=struct.unpack_from(">"+str(longdata)+"s",datagram,14)[0]
        ack_num=0
        res=0
        ack=0
        typemsg=4
        user=self.serverProxy.getUserById(userId)
        userCurrentRoom=user.userChatRoom
        self.envoiAck(self.ack_numAenvoye[user.userName],user.userAddress)
        userList=self.serverProxy.getUserList()
        for u in userList:
            if ((u.userChatRoom == userCurrentRoom) and ( u.userId!=userId)):
                buf= ctypes.create_string_buffer(LengthDatagram)
                header=(typemsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num[u.userName])
                formatMsg=">LHHLH"+str(longdata)+"s"
                struct.pack_into(formatMsg, buf,0,header,LengthDatagram,userId,0,0,message)
                self.EnvoiMsg(buf,u.userAddress,u.userName)


#*******************Fonction envoie message*****************************************************
    def EnvoiMsg(self ,buf,(host, port),userName):
        self.transport.write(buf.raw,(host, port))
        print "on incrémente le seq num de "
        print userName
        print "le num seq est don egal a:"
        self.seq_num[userName]+=1
        self.seq_num[userName] = self.seq_num[userName] % 4096
        print self.seq_num[userName]

            
#*******************Fonction Envoi Ack**********************************************************
    def envoiAck(self,ackNum,(host, port)):
        typeMsg=15
        ack=1
        res=0
        seq_num=0
        buf = ctypes.create_string_buffer(6)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ackNum<<13)|(seq_num)
        struct.pack_into(">LH", buf,0,header,6)
        self.transport.write(buf.raw,(host, port))


#*******************Fonction ConstructeurMovieId**********************************************************
    def definitionRoomName(self ,datagram):
        Movielist=self.serverProxy.getMovieList()
        IpAdress=struct.unpack_from(">BBBB",datagram,8)
        IpAdressMovie=str(IpAdress[0])+'.'+str(IpAdress[1])+'.'+str(IpAdress[2])+'.'+str(IpAdress[3])
        portMovie=struct.unpack_from(">H",datagram,12)[0]
        movieTitle=""
        for movie in Movielist:
            if (movie.movieIpAddress==IpAdressMovie)and(movie.moviePort==portMovie):
	            movieTitle=movie.movieTitle
	            break
        return movieTitle


    
	
	
	
		

                
     
            
        










	   



       
