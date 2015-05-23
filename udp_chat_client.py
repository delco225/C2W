# -*- coding: utf-8 -*-
from twisted.internet.protocol import DatagramProtocol
from c2w.main.lossy_transport import LossyTransport
import logging
from c2w.main.constants import ROOM_IDS
from c2w.main.user import c2wUser
from c2w.main.client_proxy import c2wClientProxy
from twisted.internet.protocol import Protocol
from c2w.main.movie import c2wMovieStore
import struct
import ctypes
from twisted.internet import reactor
logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_client_protocol')
userStatus={     
            'mainRoom':0,
            'movieRoom':1,
			'waitingMainRoomUserList':2,
            'waitingMovieList':3,
            'waitingMainRoom':4,
            'waitingMovieRoom':5,
            'waitingfMovieRoomUserList':6,
			'waitingAck':7,
			'disconnected':8
            
        }


class c2wUdpChatClientProtocol(DatagramProtocol):
#*********************Constructeur class c2wUdpChatClientProtocol*************************
    def __init__(self, serverAddress, serverPort, clientProxy, lossPr):

        self.serverAddress = serverAddress
        self.serverPort = serverPort
        self.clientProxy = clientProxy
        self.lossPr = lossPr
        self.userStatus=userStatus['disconnected']
        self.seq_num=0
        self.userName=""
        self.userId=0
        self.RoomName=ROOM_IDS.MAIN_ROOM 
        self.listUser=[] # on initialise une liste pour chaque utilisateur
        self.listUser_Id=[] #on initialise une liste de correspandance user-ID
        self.listMovies=[]
        self.nb_received_listUser=0 # pour savoir si c'est la 1ère fois qu'on reçoit la liste ou pas(1ère connexion ou update)
        self.nb_received_listMovie=0 #de même pour la liste movie (on evite de la recevoir 2fois)
        self.listUserReceived=0
        self.movielistRecived=0
        self.listUserRecived=0
        self.typemsgenvoye=""
        self.typemsgRecived=""
        self.MovieStore=c2wMovieStore()
        self.thisRoomName=None
        self.retransmit=None
       
#*******************************************************************************************
    def startProtocol(self):
       
        self.transport = LossyTransport(self.transport, self.lossPr)
        DatagramProtocol.transport = self.transport
#**********************Demande de connexion************************************************
    def sendLoginRequestOIE(self, userName):
        ack_num=0
        typeMsg=1
        ack=0
        res=0
        self.userName=userName
        self.typemsgenvoye="1"
        buf = ctypes.create_string_buffer(len(userName)+6)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
        formatDatagram = '>LH' + str(len(userName)) + 's'
        longdata=len(userName)+6
        struct.pack_into(formatDatagram, buf,0,header,longdata,userName)
        self.EnvoiMsg(buf)

        
        

#*********************Reception datagram**************************************************************

    def datagramReceived(self, datagram, (serverAddress, serverPort)):
        ack_bit=0
        print "je m'arrete laaaaa"
        LengthDatagram=struct.unpack_from(">LH",datagram)[1]
        header=struct.unpack_from(">LH",datagram)[0]  #H
        typeMsg=header>>28
        ack_bit=(header>>27)&1
        print typeMsg
        ack_numAenvoye= (header & 8191)
        print "**********************le num de ack est ******************** :%d" %ack_numAenvoye
        print ack_bit
        if (ack_bit==1):
            print "j'arrete la retransmission"
            self.retransmit.cancel()
        if (typeMsg==14):
            self.msgreceived="14"
            self.userStatus =userStatus['waitingMainRoomUserList'] #update du statut du user
            self.userId=struct.unpack_from(">LHH",datagram)[2]   #récupération de l'Id du user
            print "Response login request received"
            self.envoiAck(ack_numAenvoye)
            print "Ack login request envoyé"
        if(typeMsg==2):
            self.receptionListUser(datagram,self.userStatus)
            self.envoiAck(ack_numAenvoye)
            print "On ack la liste"
            self.nb_received_listUser=1
        if(typeMsg==3):
            print "Reception movielist"
            if (self.nb_received_listMovie==0):
                self.receptionListMovie(datagram)
                self.nb_received_listMovie+=1
                print "Envoi ack movielist"
                self.envoiAck(ack_numAenvoye)
                self.nb_received_listMovie=1
                if(self.nb_received_listUser==1) and (self.nb_received_listMovie==1):
                    self.clientProxy.initCompleteONE(self.listUser, self.listMovies)
                    self.userStatus=userStatus['mainRoom']
        if (typeMsg==4):
            self.ReceptionPublicMsg(datagram,LengthDatagram)
            self.envoiAck(ack_numAenvoye)
        if(typeMsg==15):
            if(self.typemsgenvoye=="6"):
                self.clientProxy.joinRoomOKONE()
                self.userStatus=userStatus['movieRoom']
                print "la méthode est exécutée"
                #self.envoiAck(ack_numAenvoye)
            if(self.typemsgenvoye=="7"):
				self.clientProxy.joinRoomOKONE()
				self.userStatus=userStatus['mainRoom']
			
            if(self.typemsgenvoye=="8"):
                print "ByeBye"
                self.clientProxy.leaveSystemOKONE()
        if(typeMsg==0):
            ErrorCode=struct.unpack_from(">LHB",datagram)[2]
            if(ErrorCode==1):
                self.clientProxy.connectionRejectedONE("Une erreur s'est produite")
            if(ErrorCode==2):
                pass
            if (ErrorCode==3):
                pass
            if (ErrorCode==4):
                pass
            
			
        

#*******************************Envoie Ack***********************************************************
    def envoiAck(self,ackNum):
        typeMsg=15
        ack=1
        res=0
        seq_num=0
        buf = ctypes.create_string_buffer(6)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ackNum<<13)|(seq_num)
        struct.pack_into(">LH", buf,0,header,6)
        self.transport.write(buf.raw,(self.serverAddress,self.serverPort))
#**********************ReceptionListUser************************************************************		
		
		
		

#************************Reception list Users**********************************************************	
    def receptionListUser(self,datagram,status):
        self.listUser=[]
        lengthMsg=struct.unpack_from(">LH",datagram)[1]
        print "%d"%lengthMsg
        lengthData=lengthMsg-8
        offset=8
        i=0
        while i< lengthData:
            lengthNameUser_Dispo=struct.unpack_from(">B",datagram,offset)[0]
            lengthNameUser=lengthNameUser_Dispo>>1
            S=lengthNameUser_Dispo&1
            Data=">BH"+ str(lengthNameUser) + "s"
            userName= struct.unpack_from(Data,datagram,offset)[2]
            userId=struct.unpack_from(Data,datagram,offset)[1]
            if (S==1):
                ROOM=ROOM_IDS.MAIN_ROOM
            else:
                ROOM=ROOM_IDS.MOVIE_ROOM
            self.listUser.append((userName,ROOM))
            self.listUser_Id.append((userName,userId))
            i+=(lengthNameUser+3)
            offset+=(lengthNameUser+3)
        liste=[]
        if status==userStatus['waitingMainRoomUserList'] or status==userStatus['mainRoom']:
            print"ici se pose le pb"
            liste=self.listUser
            print liste
        elif status==userStatus['waitingfMovieRoomUserList'] or status==userStatus['movieRoom']:
            print "******************on entre dans cette boucle************************"
            i=0
            while i<len(self.listUser):
                liste.append((self.listUser[i][0],self.thisRoomName))
                i+=1
        if status==userStatus['mainRoom'] or status==userStatus['movieRoom']:
	            self.clientProxy.setUserListONE(liste)
#**********************************Reception ListeMovie*********************************************************
    def receptionListMovie(self,datagram):
        nbMovies=struct.unpack_from(">LHH",datagram)[2]
        offset=8
        i=0 
        while i < nbMovies:
            IpAdressMovie1=struct.unpack_from(">BBBBHB",datagram,offset)[0]
            IpAdressMovie2=struct.unpack_from(">BBBBHB",datagram,offset)[1]
            IpAdressMovie3=struct.unpack_from(">BBBBHB",datagram,offset)[2]
            IpAdressMovie4=struct.unpack_from(">BBBBHB",datagram,offset)[3]
            IpAdressMovie=str(IpAdressMovie1) + "." +str(IpAdressMovie2) + "." +str(IpAdressMovie3) + "." +str(IpAdressMovie4)
            portMovie=struct.unpack_from(">LHB",datagram,offset)[1]
            lengthNameMovie=struct.unpack_from(">LHB",datagram,offset)[2]
            offset+=7
            formatMovieName=">"+ str(lengthNameMovie) + "s"
            MovieName= struct.unpack_from(formatMovieName,datagram,offset)[0]
            self.listMovies.append((MovieName,IpAdressMovie,portMovie))
            self.MovieStore.createAndAddMovie(MovieName,IpAdressMovie,portMovie,None,None,False,None)

            i+=1
            offset+=lengthNameMovie

#******************************************SendJoinRoomRequestOIE**********************************

    def sendJoinRoomRequestOIE(self,roomName):
        self.thisRoomName=roomName
        ack_num=0
        res=0
        ack=0
        if (roomName!=ROOM_IDS.MAIN_ROOM):
            self.userStatus=userStatus['waitingfMovieRoomUserList']
            self.typemsgenvoye="6"
            typeMsg=6
            msgLength=14
            Movie=self.MovieStore.getMovieByTitle(roomName)
            print Movie.movieTitle
            IpAdressMovie=Movie.movieIpAddress
            print IpAdressMovie
            MoviePort=Movie.moviePort
            buf=ctypes.create_string_buffer(14)
            header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
            Tab=IpAdressMovie.split('.')
            print Tab
            struct.pack_into(">LHHBBBBH", buf,0,header,msgLength,self.userId,int(Tab[0]),int(Tab[1]),int(Tab[2]),int(Tab[3]),MoviePort)
            self.EnvoiMsg(buf)
        else:
            typeMsg=7
            self.userStatus=userStatus['waitingMainRoom']
            self.typemsgenvoye="7"
            msgLength=8
            buf=ctypes.create_string_buffer(8)
            header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
            struct.pack_into(">LHH", buf,0,header,msgLength,self.userId)
            self.EnvoiMsg(buf)
        print "Request join movie room envoyé"

#***************************************SendChatMessage**********************************************
    def sendChatMessageOIE(self, message):
        typeMsg=4
        self.typemsgenvoye="4"
        ack=0
        res=0
        ack_num=0
        lengthDatagram=len(message)+len(self.userName)+15
        Message=message
        buf = ctypes.create_string_buffer(lengthDatagram)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
        if(self.RoomName==ROOM_IDS.MAIN_ROOM):
            formatDatagram=">LHHLH"+str(len(Message))+"s"
            print "********************%d"%self.userId
            struct.pack_into(formatDatagram, buf,0,header,lengthDatagram,self.userId,0,0,Message)
        elif(self.RoomName==ROOM_IDS.MOVIE_ROOM):
            Movie=self.c2wMovie.getMovieByTitle(self.RoomName)
            IpAdressMovie=Movie.movieIpAddres
            MoviePort=Movie.moviePort
            Tab=IpAdressMovie.split('.')
            formatDatagram=">LHHBBBBH"+str(len(Message))+"s"
            struct.pack_into(formatDatagram, buf,0,header,msgLength,self.userId,Tab[0],Tab[1],Tab[2],Tab[3],MoviePort,Message)
        self.EnvoiMsg(buf)
        print "Request send chat Msg envoyé"

#**********************EnvoiMsg********************************************************
    def EnvoiMsg(self ,buf,nbenvoi=0):
        if (nbenvoi==0):
            self.transport.write(buf.raw,(self.serverAddress, self.serverPort))
            self.seq_num+=1
            self.seq_num = self.seq_num % 4096
            nbenvoi+=1
        else:
            self.transport.write(buf.raw,(self.serverAddress, self.serverPort))
        self.retransmit=reactor.callLater(2.0,self.EnvoiMsg,buf,nbenvoi)
            

#**********************ReceptionPublicMsg**********************************************
    def ReceptionPublicMsg(self,buf,LengthDatagram):
        
        userId=struct.unpack_from(">LHH",buf)[2]
        i=0
        userName=""
        print self.listUser_Id
        while i<len(self.listUser_Id):
            if(self.listUser_Id[i][1]==userId):
                userName=self.listUser_Id[i][0]
                break
            else:
                i+=1
        lengthMsg=LengthDatagram-14
        formatMsg=">"+str(lengthMsg)+"s"
        Msg= struct.unpack_from(formatMsg, buf,14)[0]
        print Msg
        print userName
        self.clientProxy.chatMessageReceivedONE(userName,Msg)
        
		
#**************************SendLeaveSystem******************************************
    def sendLeaveSystemRequestOIE(self):

        typeMsg=8
        self.typemsgenvoye="8"
        ack=0
        res=0
        ack_num=0
        lengthDatagram=8
        buf = ctypes.create_string_buffer(lengthDatagram)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
        struct.pack_into(">LHH", buf,0,header,lengthDatagram,self.userId)
        self.EnvoiMsg(buf)
        print "demande de deconnexion envoyee"

