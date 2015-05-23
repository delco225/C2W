# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
from c2w.main.client_model import c2wClientModel
import logging
import struct
import ctypes
from c2w.main.constants import ROOM_IDS
from c2w.main.user import c2wUser
from c2w.main.movie import c2wMovieStore
from c2w.main.client_proxy import c2wClientProxy

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.tcp_chat_client_protocol')
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

class c2wTcpChatClientProtocol(Protocol):

    def __init__(self, clientProxy, serverAddress, serverPort):
        self.serverAddress = serverAddress
        self.serverPort = serverPort
        self.clientProxy = clientProxy
        self.RoomName=ROOM_IDS.MAIN_ROOM
        self.userName=""
        self.msgenvoye=""
        self.msgreceived=""
        self.userStatus=userStatus['disconnected']
        self.seq_num=0
        self.stockedData=ctypes.create_string_buffer(0)
        self.listUser_Id=[]
        self.listUser=[]
        self.listMovies=[]
        self.MovieStore=c2wMovieStore()
        self.nb_received_listMovie=0
        self.nb_received_listUser=0
        self.typemsgenvoye=""
        self.traitement=False
        self.userId=""
        

#**********************SendLoginRequest******************************************

    def sendLoginRequestOIE(self, userName):
        ack_num=0
        typeMsg=1
        ack=0
        res=0
        self.userName=userName
        self.msgenvoye="1"
        buf = ctypes.create_string_buffer(len(userName)+6)
        print "oui elle marche"
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
        formatPacket = '>LH' + str(len(userName)) + 's'
        longdata=len(userName)+6
        struct.pack_into(formatPacket, buf,0,header,longdata,userName)
        self.transport.write(buf.raw)
        moduleLogger.debug('loginRequest called with username=%s', userName)
#*************************Reception avec Framing*************************************
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
#******************************FonctionTraitementData*********************************

    def traitementData(self,packet):
        print "On traite un message"
        Lengthpacket=struct.unpack_from(">LH",packet)[1]
        header=struct.unpack_from(">LH",packet)[0]
        typeMsg=header>>28
        print typeMsg
        ack_numAenvoye= (header & 8191)
        print "**********************le num de ack est ******************** :%d" %ack_numAenvoye
        if (typeMsg==14):
            self.msgreceived="14"
            self.userStatus =userStatus['waitingMainRoomUserList']
            self.userId=struct.unpack_from(">LHH",packet)[2]
            print "Response received"
            self.envoiAck(ack_numAenvoye)
            self.seq_num +=1
            self.seq_num= self.seq_num % 4096
            print "Ack du user Id envoyé"
        if(typeMsg==2):
            self.receptionListUser(packet,self.userStatus)
            self.envoiAck(ack_numAenvoye)
            self.nb_received_listUser+=1
            if(self.nb_received_listUser==1) and (self.nb_received_listMovie==1):
                    self.clientProxy.initCompleteONE(self.listUser, self.listMovies)
                    self.userStatus=userStatus['mainRoom']
            print "ack de user list envoyé"
        if(typeMsg==3):
            print "Reception movielist"
            if (self.nb_received_listMovie==0):
                self.receptionListMovie(packet)
                self.nb_received_listMovie+=1
                print "Envoi ack movielist"
                self.nb_received_listMovie=1 
                self.envoiAck(ack_numAenvoye)              
        if (typeMsg==4):
            print "reception message"
            self.ReceptionPublicMsg(packet,Lengthpacket)
            self.envoiAck(ack_numAenvoye)
        if(typeMsg==15):
            if(self.typemsgenvoye=="6"):
                self.clientProxy.joinRoomOKONE()
                self.userStatus=userStatus['movieRoom']
                print "la méthode est exécutée"
                self.envoiAck(ack_numAenvoye)
                
            if(self.typemsgenvoye=="7"):
				self.clientProxy.joinRoomOKONE()
				self.userStatus=userStatus['mainRoom']

            if(self.typemsgenvoye=="8"):
                print "ByeBye"
                self.clientProxy.leaveSystemOKONE()
        if (typeMsg==0):
            print "on entre ici la ou on doit traiter the same user Name"
            errorCode=struct.unpack_from(">LHB",packet)[2]
            if(errorCode==1):
                self.clientProxy.connectionRejectedONE("Impossible de se connecter Username already exist")
                    


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
#*******************Fonction envoie message*****************************************************
    def EnvoiMsg(self,buf):
        self.transport.write(buf.raw)
        print "................................................................."
        print self.seq_num
        self.seq_num+=1
        self.seq_num = self.seq_num % 4096  

#************************Reception list Users**********************************************************	
    def receptionListUser(self,packet,status):
        self.listUser=[]
        lengthMsg=struct.unpack_from(">LH",packet)[1]
        print "00000000000000000000on reçoit la list0000000000000000000"
        lengthData=lengthMsg-8
        offset=8
        i=0
        while i< lengthData:
            lengthNameUser_Dispo=struct.unpack_from(">B",packet,offset)[0]
            lengthNameUser=lengthNameUser_Dispo>>1
            S=lengthNameUser_Dispo&1
            Data=">BH"+ str(lengthNameUser) + "s"
            userName= struct.unpack_from(Data,packet,offset)[2]
            userId=struct.unpack_from(Data,packet,offset)[1]
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
            liste=self.listUser
        elif status==userStatus['waitingfMovieRoomUserList'] or status==userStatus['movieRoom']:
            print "******************on entre dans cette boucle************************"
            i=0
            while i<len(self.listUser):
                liste.append((self.listUser[i][0],self.RoomName)) # il y'avait self.thisRoomName???
                i+=1
        if status==userStatus['mainRoom'] or status==userStatus['movieRoom']:
                self.clientProxy.setUserListONE(liste)
                print "§!§§§§§§§§§§§§§§§update ok "

#**********************************Reception ListeMovie*********************************************************
    def receptionListMovie(self,packet):
        len(packet)
        nbMovies=struct.unpack_from(">LHH",packet)[2]
        print "Nb movies reçu %d",nbMovies
        offset=8
        i=0 
        while i < nbMovies:
            IpAdressMovie1=struct.unpack_from(">BBBBHB",packet,offset)[0]
            IpAdressMovie2=struct.unpack_from(">BBBBHB",packet,offset)[1]
            IpAdressMovie3=struct.unpack_from(">BBBBHB",packet,offset)[2]
            IpAdressMovie4=struct.unpack_from(">BBBBHB",packet,offset)[3]
            IpAdressMovie=str(IpAdressMovie1) + "." +str(IpAdressMovie2) + "." +str(IpAdressMovie3) + "." +str(IpAdressMovie4)
            portMovie=struct.unpack_from(">LHB",packet,offset)[1]
            lengthNameMovie=struct.unpack_from(">LHB",packet,offset)[2]
            offset+=7
            formatMovieName=">"+ str(lengthNameMovie) + "s"
            MovieName= struct.unpack_from(formatMovieName,packet,offset)[0]
            self.listMovies.append((MovieName,IpAdressMovie,portMovie))
            self.MovieStore.createAndAddMovie(MovieName,IpAdressMovie,portMovie,None,None,False,None)
            i+=1
            offset+=lengthNameMovie
        print self.listMovies

#***************************************SendChatMessage**********************************************
    def sendChatMessageOIE(self, message):
        self.typemsgenvoye=4
        typeMsg=4
        ack=0
        res=0
        ack_num=0
        lengthDatagram=len(message)+len(self.userName)+9
        Message=message
        buf = ctypes.create_string_buffer(lengthDatagram)
        header=(typeMsg<<28)|(ack<<27)|(res<<26)|(ack_num<<13)|(self.seq_num)
        if(self.RoomName==ROOM_IDS.MAIN_ROOM):
            print "envoie de message main room cote client"
            formatDatagram=">LHHLH"+str(len(Message))+"s"
            print "********************%d"%self.userId
            struct.pack_into(formatDatagram, buf,0,header,lengthDatagram,self.userId,0,0,Message)
            self.EnvoiMsg(buf)
        else:
            print "on a envoyé la request pour chat movie room"
            Movie=self.MovieStore.getMovieByTitle(self.RoomName)
            IpAdressMovie=Movie.movieIpAddress
            MoviePort=Movie.moviePort
            Tab=IpAdressMovie.split('.')
            formatDatagram=">LHHBBBBH"+str(len(Message))+"s"
            struct.pack_into(formatDatagram, buf,0,header,lengthDatagram,self.userId,int(Tab[0]),int(Tab[1]),int(Tab[2]),int(Tab[3]),MoviePort,Message)
            self.EnvoiMsg(buf)
        print "Request send chat Msg envoyé"

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

#******************************************SendJoinRoomRequestOIE**********************************

    def sendJoinRoomRequestOIE(self,roomName):
        self.RoomName=roomName      # il y'avait self.thisRoomName???
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



