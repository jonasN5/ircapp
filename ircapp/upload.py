#!/usr/bin/python3



import sys
import os
import struct
import irc.client
import requests
import threading
import time
import datetime
from ircapp.logs import log
from ircapp.models import *
import random, string
from django.utils.timezone import now as utcnow
from jaraco.stream import buffer
import miniupnpc
import socket
from multiprocessing import Queue
import main, settings
import re



def upload_monitoring(self, connection, upload):
    sz = 0
    log("Monitoring started").write()
    start = time.time()
    while connection.connected:
        if self.bytesSent != sz:
            end = time.time()
            percentage = int(self.position + self.bytesSent) / int(self.size) * 100
            completed = int(self.position + self.bytesSent)
            elapsed = end-start
            speed = int((self.bytesSent-sz)/elapsed)
            if speed != 0:
                tm = (int(self.size)-int(self.bytesSent)-self.position) / speed
            else:
                tm = 99999
            eta = utcnow() + datetime.timedelta(seconds=tm)

            speed = int(speed/1024)
            upload.status, upload.progress, upload.completed, upload.eta, upload.timeleft = 'Uploading...', percentage, completed, eta, tm
            #workaround for occasionnal empty packages
            if speed:
                upload.speed = speed
            upload.save()

            sz = self.bytesSent
            start = time.time()
            if percentage >=100:
                self.reactor.disconnect_all()
                return ""
        time.sleep(1)
    log("Monitoring stoped").write()
    

class ModifiedReactor(irc.client.Reactor):
    def dcc(self, dcctype="chat"):
        """
        override method to use new DCCConnection in order to support port argument
        """
        with self.mutex:
            c = ModifiedDCCConnection(self, dcctype)
            self.connections.append(c)
        return c
        
        
class ModifiedDCCConnection(irc.client.DCCConnection):
    def listen(self, port):
        """
        override method in order to support port argument
        nothing changed in the method except :
        self.socket.bind(('', port))
        Required in order to support port argument and external IP binding
        """
        self.buffer = buffer.LineBuffer()
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 1
        try:
            self.socket.bind(('', port))
            self.localaddress, self.localport = self.socket.getsockname()
            self.socket.listen(10)
        except socket.error as x:
            raise DCCConnectionError("Couldn't bind socket: %s" % x)
        return self
        
    
class DCCSend(irc.client.SimpleIRCClient):
    """
    override the reactor class to add port argument
    """
    reactor_class = ModifiedReactor
    
    
    def __init__(self, filename, nickname, password, upload):
        irc.client.SimpleIRCClient.__init__(self)
        self.size = os.path.getsize(filename)
        self.filename = filename
        self.cancel = False
        self.position = 0
        self.password = password
        self.nickname = self.bot = nickname
        self.externalip = None
        self.file = None
        self.dcc = None
        self.upnp = None
        self.eport = None
        self.bytesSent = 0
        self.upload = upload
        

    def on_welcome(self, connection, event):
        c = self.connection
        c.whois(event.target)
        PORT = None
        t=threading.Timer(0, self.signal_listener, [connection, event])
        t.daemon=True
        t.start()        
        with open(os.path.join(settings.BASE_DIR, "config.ini"), "r") as cfg:
            content = cfg.readlines()
            PORT = content[2][1+content[2].index("="):content[2].index("#")].strip(" ")
            cfg.close()
        if PORT:
            #manual port forwarding used
            PORT = int(PORT)
            self.dcc = self.dcc_listen(dcctype="raw", port=PORT)
        else:
            self.dcc = self.dcc_listen(dcctype="raw")
            try:
                self.prepupnp()
            except Exception as e:
                log("Couldn't create port mapping. Is upnp supported and activated ?").write()
                c.quit()
                return
        #we need to wait to get the externalip address, therefore spawn a deamon thread
        s=threading.Timer(0, self.dccsend, [connection])
        s.daemon=True
        s.start()
    
    def dccsend(self, c):
        while not self.externalip:
            time.sleep(0.2)
        filename = os.path.basename(self.filename)
        self.upload.sizeraw = self.size
        self.upload.save()
        c.ctcp("DCC", self.nickname, "SEND %s %s %d %d %s" % (
            filename,
            irc.client.ip_quad_to_numstr(self.externalip),
            self.dcc.localport,
            self.size,
            self.password))    
    
    
    def signal_listener(self, connection, event):
        botqueue = main.queuedict[connection.server+self.bot]
        while True:
            while botqueue.empty():
                time.sleep(0.2)
            mystring = botqueue.get()
            print ("Signal received on %s: %s" % (connection.server+':'+self.bot, mystring))
            if "cancel" in mystring:
                #this is the case when there are no more DCCconnections or when IRCapp shutdown is pressed
                self.reactor.disconnect_all()
                break
        
        
    def prepupnp(self):
        """
        prep upnp
        """
        self.upnp = miniupnpc.UPnP()

        self.upnp.discoverdelay = 200

        try:
            ndevices = self.upnp.discover()
            print (ndevices, 'device(s) detected')
            # select an igd
            self.upnp.selectigd()
            """
            check database for previous port mapping ;
            check if port mapping still exist ; if so, delete it
            
            if check database for port mapping:
                try:
                    u.deleteportmapping(port, 'TCP')
                except NoSuchEntryInArray:
                    print("port mapping already deleted")
            """        
            # display information about the IGD and the internet connection
            externalipaddress = self.upnp.externalipaddress()
            print (self.upnp.statusinfo(), self.upnp.connectiontype())

            self.eport = self.dcc.localport

            # find a free port for the redirection
            r = self.upnp.getspecificportmapping(self.eport, 'TCP')
            while r != None and self.eport < 65536:
	            self.eport = self.eport + 1
	            r = self.upnp.getspecificportmapping(self.eport, 'TCP')

            log('trying to redirect %s port %u TCP => %s port %u TCP' % (externalipaddress, self.eport, self.upnp.lanaddr, self.dcc.localport)).write()

            b = self.upnp.addportmapping(self.eport, 'TCP', self.upnp.lanaddr, self.dcc.localport,
                                'UPnP IGD Tester port %u' % self.eport, '')
            if b:
	            log('Success').write()

            else:
	            log('Failed').write()

        except Exception as e:
            log('UPnP exception :', e).write()    

    def dcc_listen(self, dcctype="chat", port=0):
        """
        overwrite method to add port argument
        """
        dcc = self.reactor.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.listen(port)
        return dcc


    def on_ctcp(self, c, e):
        if e.arguments[0] == "DCC":
            self.on_dccsend(c, e)
        if e.arguments[0] == "CHAT":
            if e.arguments[1] == "wrong password":
                upload.status = 'Wrong password'
                upload.save()
                self.reactor.disconnect_all()
                """
                need to add the possibility to retype password
                """            


    def on_dcc_connect(self, c, e):
        t = threading.Timer(0, upload_monitoring, [self, c, self.upload])
        t.start()    
        log("connection made with %s" % self.nickname).write()
        self.file = open(self.filename, 'rb')
        self.sendBlock()


    def sendBlock(self):
        if self.position > 0:
            self.file.seek(self.position)
        block = self.file.read(2**25)
        if block:
            self.dcc.send_bytes(block)
            self.bytesSent = self.bytesSent + len(block)
        else:
            # Nothing more to send, transfer complete.
            self.connection.quit()
            
    def on_dccsend(self, c, e):
        if e.arguments[1].split(" ", 1)[0] == "RESUME":
            self.position = int(e.arguments[1].split(" ")[3])
            c.ctcp("DCC", self.nickname, "ACCEPT %s %d %d" % (
            os.path.basename(self.filename),
            self.eport,
            self.position))



    def on_dccmsg(self, connection, event):
        data = event.arguments[0][-8:]
        bytesAcknowledged = struct.unpack("!Q", data)[0]
        if bytesAcknowledged < self.bytesSent:
            return
        elif bytesAcknowledged > self.bytesSent:
            self.connection.quit()
            return
        self.sendBlock()


    def on_dcc_disconnect(self, connection, event):
        self.file.close()
        self.upnp.deleteportmapping(self.eport, 'TCP')
        log("Portmapping for port %d deleted" % self.eport).write()
        log("DCC connection closed").write()
        try:
            self.connection.quit()
        except:
            pass



    def on_disconnect(self, connection, event):
        log("disconnected").write()
        self.upload.delete()

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")
        log("Nickname already used. Now using %s" % (c.get_nickname() + "_")).write()

    def on_whoisactually(self, c, e):
        #this event contains our public IP address
        for x in e.arguments:
            self.externalip = re.findall( r'[0-9]+(?:\.[0-9]+){3}', x )
            if self.externalip:
                self.externalip = self.externalip[0]
                log("External IP obtained from IRC server: %s" % self.externalip).write()
                break

def DCC_deamonthread(c, server, nickname, upload):
    botqueue = main.queuedict[server+c.bot] = Queue()
    i=1    
    while True:
        try:
            c.connect(server, 6667, nickname)
            c.start()
            break
        except irc.client.ServerConnectionError as x:
            log("error (%s)" % i + str(x)).write()
            upload.status, upload.active = "Error during connection", False
            upload.save()
            i+=1
            if not botqueue.empty():
                mystring = botqueue.get()
                if "cancel" in mystring:
                    upload.delete()
                    break

            
def upload_file(filename, rec_nick, pw):
    server = "irc.rizon.net" #good server that uses IP cloaking (public IP masked)
    irc.events.numeric["338"] = "whoisactually" #numeric on rizon where IP address is replied to a WHOIS command  

    irc.client.ServerConnection.buffer_class.encoding = 'latin-1'
    upload = Upload_Ongoing(filename=filename,status="Connecting to server...", active=True, server=server, username=rec_nick)
    upload.save()
    c = DCCSend(filename, rec_nick, pw, upload)
    nickname = ''.join(random.choice(string.ascii_lowercase) for i in range(10))   
    t = threading.Thread(target=DCC_deamonthread, args=(c, server, nickname, upload))
    t.daemon=True
    t.start()
    #factory = Factory(bind_address=(os.environ['OPENSHIFT_PYTHON_IP'], 0))

