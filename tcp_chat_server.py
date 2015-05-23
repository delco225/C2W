# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
from c2w.main.server_proxy import c2wServerProxy
import logging
import struct
import ctypes
from c2w.main.constants import ROOM_IDS
from c2w.main.user import c2wUser

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.tcp_chat_server_protocol')


class c2wTcpChatServerProtocol(Protocol):

    def __init__(self, serverProxy, clientAddress, clientPort):
    
        self.clientAddress = clientAddress
        self.clientPort = clientPort
        self.serverProxy = serverProxy
        self.seq_num=0
        self.userId=0
        self.nbConnectedUser=0
        self.typeMsgRecievedPrecedant=""  
        self.typeMsgSentPrecedant=""
        self.stockedData=ctypes.create_string_buffer(0)
        self.traitement=False
#*************************Reception avec Framing******************************
    def dataReceived(self, data):
        self.traitement=False
        longStockedData=len(self.stockedData)
        buf=ctypes.create_string_buffer(longStockedData)
        buf=self.stockedData
        longMsg=longStockedData+len(data)
        self.stockedData=ctypes.create_string_buffer(longMsg)
        self.stockedData[0:longStockedData]=buf
        self.stockedData[longStockedData:longMsg]=data
        longStockedData=len(self.stockedData)
        while (longStockedData>=6) and (self.traitement==False):
            lengthMsg= struct.unpack_from('>LH',self.stockedData)[1]
            if (longStockedData>= lengthMsg):
                Msg= ctypes.create_string_buffer(lengthMsg)
                Msg= self.stockedData[0:lengthMsg]
                longrestData=longStockedData-lengthMsg
                buf=self.stockedData[lengthMsg:lengthMsg+longrestData]
                self.stockedData=ctypes.create_string_buffer(longrestData)
                self.stockedData=buf
                self.traitementData(Msg)
                longStockedData=longrestData
            else:
                self.traitement=True
                print "on a tout traité"

#*********************************************************************************************************************************			
#			                                Useful Function
#			
#*******************************************************************************************************************************




#**************************************TraitementMsgReçuComplet***************************
    def traitementData(self,packet):
        LengthPacket=struct.unpack_from('>LH',packet)[1]
        LengthData=LengthPacket-6
        msg_recu=struct.unpack_from(">LH"+str(LengthData)+"s",packet)
        header=msg_recu[0]
        data=msg_recu[2]
        typeMsg=header>>28
        ack_numRecu=header>>13 & 8191
        ack_numAenvoye=header & 8191
#+++++++++++++++++++++++++ TypeMsg=1(loginrequest)+++++++++++++++++++++++++
        if(typeMsg==1):
            print "on entre dans la boucle "
            print data
            print self.serverProxy.userExists(data)
            if (self.serverProxy.userExists(data)==True):
                errorCode=1
                typeMsg=0
                ack=1
                res=0
                buf= ctypes.create_string_buffer(7)
                header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_numAenvoye<<13)|(self.seq_num)
                struct.pack_into('>LHB', buf,0,header,7,errorCode)
                self.EnvoiMsg(buf)
            else :     
                typeMsg=14
                ack=1
                res=0
                self.userId=self.serverProxy.addUser(data,ROOM_IDS.MAIN_ROOM,self,None)
                user=self.serverProxy.getUserById(self.userId)
                buf= ctypes.create_string_buffer(8)
                header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_numAenvoye<<13)|(self.seq_num)
                struct.pack_into('>LHH', buf,0,header,8,self.userId)
                self.EnvoiMsg(buf)
                if(len(self.serverProxy.getUserList())>1):
                    userList=self.serverProxy.getUserList()
                    for u in userList:
                        if (u.userName is not user.userName):
                            u.userChatInstance.sendlistUserMainRoom()
                self.typeMsgRecievedPrecedant="1"  
                self.typeMsgSentPrecedant="14"
#+++++++++++++++++++++++++++TypeMsg=15(ACK)+++++++++++++++++++++++++++++++++++++++++
        if(typeMsg==15):
            print("on reçoit ACK")
            print ack_numRecu
            if (ack_numRecu== (self.seq_num-1)):
                print"***************num ACK correct**********"
                if (self.typeMsgRecievedPrecedant=="1" and self.typeMsgSentPrecedant=="14"):
                    print"*****Envoi de la liste Movie*****************"
                    self.sendlistMovie(0,self.seq_num)
                    print"listeMovieSent"
                    self.typeMsgRecievedPrecedant="15"
                    self.typeMsgSentPrecedant="3"
                    print"****************"
                elif (self.typeMsgRecievedPrecedant=="15" and self.typeMsgSentPrecedant=="3"):
                    print"**********Envoie de Userlist********"
                    self.sendlistUserMainRoom()
                    
                    self.typeMsgRecievedPrecedant="15"
                    self.typeMsgSentPrecedant="2"
                    print "************************************************************"
                else:
                    pass
					 
#+++++++++++++++++++++++++++TypeMsg=4(EnvoieMsgPubliqueListeUser)+++++++++++++++++++++++++++++++++++++++++
        if(typeMsg==4):
            print "type message 4"
            self.envoiAck(ack_numAenvoye)
            print ack_numAenvoye
            user=self.serverProxy.getUserById(self.userId)
            userCurrentRoom=user.userChatRoom
            userList=self.serverProxy.getUserList()
            print user.userChatRoom
            for u in userList:
                if (u.userChatRoom == user.userChatRoom) and ( u.userId!=self.userId):
                    print "y'a til envoi de msg dans movie room ?"
                    u.userChatInstance.envoiPublicMsgMainRoom(packet,LengthPacket)
#+++++++++++++++++++++++++++TypeMsg=6(RequestJoinMovieRoom)+++++++++++++++++++++++++++
        if(typeMsg==6):
            user=self.serverProxy.getUserById(self.userId)
            print"le serveur comprend le msg on y est "
            self.envoiAck(ack_numAenvoye)
            userId=struct.unpack_from(">H",packet,6)[0]
            movieTitle=self.definitionRoomName(packet)
            print movieTitle
            user.userChatRoom=movieTitle
            print "ccccccccccccccccccc"
            print user.userChatRoom
            self.serverProxy.startStreamingMovie(movieTitle)
            userList=self.serverProxy.getUserList()
            print userList
            for u in userList:
                if (u.userChatRoom==ROOM_IDS.MAIN_ROOM):
                    u.userChatInstance.sendlistUserMainRoom()
            for u in userList:
                if (u.userChatRoom==movieTitle):
                    print u.userName
                    u.userChatInstance.sendlistUserMovieRoom(movieTitle)
                    print "On entre dans la boucle d'envoie liste Update"
            self.serverProxy.updateUserChatroom(user.userName, movieTitle)     #update du room du user (ici newroom=movieRoom)
#+++++++++++++++++++++++++++TypeMsg=7(RequestJoinMainRoom)+++++++++++++++++++++++++++               

        if(typeMsg==7):
            user=self.serverProxy.getUserById(self.userId)
            self.envoiAck(ack_numAenvoye)
            userId=struct.unpack_from(">H",packet,6)[0]
            MovieRoomNameToLeave=user.userChatRoom
            self.serverProxy.stopStreamingMovie(user.userChatRoom)# a voir si ceci influe sur les autres qui regardent le mm filme
            user.userChatRoom=ROOM_IDS.MAIN_ROOM
            userList=self.serverProxy.getUserList()
            for u in userList:
                if (u.userChatRoom==ROOM_IDS.MAIN_ROOM):
                    u.userChatInstance.sendlistUserMainRoom()
            for u in userList:
                if (u.userChatRoom==MovieRoomNameToLeave):
                    u.userChatInstance.sendlistUserMovieRoom(MovieRoomNameToLeave)
#+++++++++++++++++++++++++++TypeMsg=8(RequestLeaveSystem)+++++++++++++++++++++++++++
        if(typeMsg==8):
            user=self.serverProxy.getUserById(self.userId) 
            print "demande de deconnexion recue"
            self.serverProxy.removeUser(user.userName)
            self.envoiAck(ack_numAenvoye)
            listUserMainRoom=self.serverProxy.getUserList()
            print listUserMainRoom 
            for u in listUserMainRoom:
                u.userChatInstance.sendlistUserMainRoom()

                    
                


#**********************************fonction ConstructionlistUser*******************************************************************

    def constructionListeUser(self,Movie=None):
        print "++++++++++++++++++++++"
        print self.seq_num
        
        typeMsg=2
        ack=0
        res=0
        ROO=0
        ack_num=0
        userList=self.serverProxy.getUserList()
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
        print userListToSend
        nb_user=len(userListToSend)
        Msg_length=Data_length+8
        buf = ctypes.create_string_buffer(Msg_length)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
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
        self.EnvoiMsg(buf)
        print ".........................."
#********************************** Envoi liste Utilisateur In the Main Room***********************	
    def sendlistUserMainRoom(self):
        self.constructionListeUser()
  
#**********************Envoie Liste Movies*******************************************
    def sendlistMovie(self,ack_num,seq_num):
        print "-----------------------"
        print seq_num
        typeMsg=3
        ack=0
        res=0
        Data_length = 0
        List_Movies=self.serverProxy.getMovieList()
        print List_Movies 
        Nb_Movies=len(List_Movies)
        print Nb_Movies
        for movie in List_Movies: 
	        Data_length += len(movie.movieTitle)+7
        Msg_length=Data_length+8	
        buf = ctypes.create_string_buffer(Msg_length) 
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(seq_num)
        struct.pack_into('>LHH',buf,0,header,Msg_length,Nb_Movies) # Header packing
        pos_buffer=8
        for movie in List_Movies:
            Tab=movie.movieIpAddress.split('.')
            print movie.movieTitle
            print("%s"%movie.movieIpAddress)
            FormatData='>BBBBHB' + str(len(movie.movieTitle)) + 's' 
            struct.pack_into(FormatData,buf,pos_buffer,int(Tab[0]),int(Tab[1]),int(Tab[2]),int(Tab[3]),movie.moviePort,len(movie.movieTitle),movie.movieTitle)# packing each movie
            pos_buffer+=len(movie.movieTitle)+7
        self.EnvoiMsg(buf)
        print "message a été bien envoyé"
#*******************Fonction envoie message*****************************************************
    def EnvoiMsg(self,buf):
        self.transport.write(buf.raw)
        self.seq_num+=1
        self.seq_num = self.seq_num % 4096  
#*******************************Envoie Ack***********************************************************
    def envoiAck(self,ackNum):
        typeMsg=15
        ack=1
        res=0
        seq_num=0
        buf = ctypes.create_string_buffer(6)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ackNum<<13)|(seq_num)
        struct.pack_into(">LH", buf,0,header,6)
        self.transport.write(buf.raw)

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
        buf= ctypes.create_string_buffer(LengthDatagram)
        header=(typemsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
        formatMsg=">LHHLH"+str(longdata)+"s"
        struct.pack_into(formatMsg, buf,0,header,LengthDatagram,userId,0,0,message)
        self.EnvoiMsg(buf)


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
#****************************Envoi liste Utilisateur in a Movie room***********************

    def sendlistUserMovieRoom(self,MovieRoomName):
        self.constructionListeUser(MovieRoomName)



