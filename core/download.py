#!/usr/bin/python3



import sys, json
import os
import errno
import struct
import argparse
import shlex
import irc.client
from irc.connection import Factory
import threading
import time
import tarfile
if sys.platform == "win32":
    os.environ['UNRAR_LIB_PATH'] = os.path.join(os.path.dirname(sys.executable), 'unrar.dll')
    from unrar import rarfile
else:
    import rarfile
import shutil
import datetime
from core.logs import directory, log
from core.models import *
import views
import random, string
from django.utils.timezone import now as utcnow
import subprocess
import cherrypy
from jaraco.stream import buffer

from multiprocessing import Queue
import main

class ModifiedReactor(irc.client.Reactor):
    def server(self):
        """Creates and returns a ServerConnection object."""

        c = MServerConnection(self)
        with self.mutex:
            self.connections.append(c)
        return c
        
        
class MServerConnection(irc.client.ServerConnection):
    def process_data(self):
        "read and process input from self.socket"

        try:
            reader = getattr(self.socket, 'read', self.socket.recv)
            new_data = reader(2 ** 14)
        except socket.error:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return

        self.buffer.feed(new_data)

        # process each non-empty line after logging all lines
        for line in self.buffer:
            if not line: continue
            self._process_line(line)

#these are the two global variables that will store History and Download_ongoing objects
def monitoring(self, connection, bot, position=0):
    sz = 0
    log("Monitoring started").write()
    while connection.connected:
        percentage = int(position + self.dict[bot]["received_bytes"]) / int(self.dict[bot]["size"]) * 100
        completed = int(position + self.dict[bot]["received_bytes"])
        speed = (self.dict[bot]["received_bytes"]-sz)
        if speed != 0:
            tm = (int(self.dict[bot]["size"])-int(self.dict[bot]["received_bytes"])-position) / speed
        else:
            tm = 99999
        eta = utcnow() + datetime.timedelta(seconds=tm)

        speed = int(speed/1024)
        (self.dict[bot]["down"].status, self.dict[bot]["down"].progress, self.dict[bot]["down"].completed, 
            self.dict[bot]["down"].eta, self.dict[bot]["down"].timeleft)= 'Downloading...', percentage, completed, eta, tm
        #workaround for occasionnal empty packages
        if speed:
            self.dict[bot]["down"].speed = speed
        self.dict[bot]["down"].save()

        sz = self.dict[bot]["received_bytes"]
        if percentage >=100:
            self.DCCconnections_dict[bot].disconnect()
            return ""
        time.sleep(1)
    log("Monitoring stoped").write()



    
class DCCReceive(irc.client.SimpleIRCClient):
    reactor_class = ModifiedReactor
    def __init__(self, direct=False, **kwargs):
        irc.client.SimpleIRCClient.__init__(self)
        """
        since one DCCReceive object can have multiple DCCconnections, we need to be able differentiate the information;
        The lists here will be used and read thanks to the unique server identifier : the nickname
        """
        self.DCCconnections_dict = {} 
        self.dict = { "direct" : { 
            "received_bytes" : 0 ,
            "cancel" : False,
            "position" : 0,
            "stop" : False,
            "down" : kwargs["down"],
            "hist" : kwargs["hist"]
        } }           
        if direct:
            self.dict[kwargs["nickname"]] = self.dict.pop("direct")
            self.dict[kwargs["nickname"]]["pw"] = kwargs["password"]
            self.dict[kwargs["nickname"]]["nick"] = self.bot = kwargs["nickname"]
            self.direct = True
            self.bot = kwargs["nickname"]
        else:
            self.dict[kwargs["bot"]] = self.dict.pop("direct") #this dict will be used to identify each DCCconnection
            self.dict[kwargs["bot"]]["bot"] = kwargs["bot"]
            self.dict[kwargs["bot"]]["msg"] = kwargs["msg"]
            self.dict[kwargs["bot"]]["channel"] = kwargs["channel"]
            self.dict[kwargs["bot"]]["size"] = kwargs["size"]
            self.dict[kwargs["bot"]]["filename"] = kwargs["filename"]
            self.direct = False
            self.bot = kwargs["bot"]

                
            
    #used as a deamon thread to listen to queue signals
    def signal_listener(self, connection, event):
        botqueue = main.queuedict[connection.server+self.bot]
        while True:
            while botqueue.empty():
                time.sleep(0.2)
            mystring = botqueue.get()
            bot = self.bot
            print ("Signal received on %s: %s" % (connection.server+':'+bot, mystring))
            if "stop" in mystring:
                #this is the case when there are no more DCCconnections or when IRCapp shutdown is pressed
                self.dict[bot]["stop"] = True
                self.reactor.disconnect_all()
                break
            elif "cancel" in mystring:
                if self.direct:
                    self.reactor.disconnect_all()
                    del botqueue
                    self.dict[bot]["down"].delete()
                    return
                #connection.privmsg(bot, "xdcc cancel")                       
                self.dict[bot]["cancel"] = True
                try:
                    self.DCCconnections_dict[bot].disconnect()
                except KeyError:
                    #DCC connection not yet established
                    self.on_dcc_disconnect(connection, event, bot=bot)
            else:
                mylist = [x for x in mystring.split(",")]
                if mylist[0] == "queue_item":
                    connection.privmsg(bot, "xdcc send #%s" % mylist[3])
                    log("New package requested").write()
                    hist = Download_History(filename=mylist[1], sizeraw=mylist[2]) 
                    self.dict[bot]["filename"], self.dict[bot]["size"], self.dict[bot]["received_bytes"] = mylist[1], mylist[2], 0
                    (self.dict[bot]["down"].status, self.dict[bot]["down"].progress, self.dict[bot]["down"].completed, 
                        self.dict[bot]["down"].eta, self.dict[bot]["down"].timeleft, self.dict[bot]["down"].active)= 'New package requested', 0, 0, None, None, True                    
                    self.dict[bot]["down"].filename, self.dict[bot]["down"].sizeraw, self.dict[bot]["down"].package_number = (
                        mylist[1], mylist[2], mylist[3])
                    self.dict[bot]["down"].save()
                    self.dict[bot]["hist"] = hist
                else:
                    main.queuedict[connection.server+mylist[1]] = Queue()
                    #remaining case : the bot has to join another channel of this server
                    #since we're about to open a new DCCconnection, create new download object
                    down = Download_Ongoing(filename=mylist[3], status="Requesting package...", active=True,
                        server=self.dict[bot]["down"].server, channel=mylist[0], username=mylist[1], package_number=mylist[2], sizeraw=mylist[4])
                    hist = Download_History(filename=mylist[3], sizeraw=mylist[4])   
                    down.save()
                    bot = self.bot = mylist[1]
                    data = {
                        "received_bytes" : 0,
                        "cancel" : False,
                        "stop" : False,
                        "position" : 0,
                        "down" : down,
                        "hist" : hist,
                        "filename" : mylist[3],
                        "size" : mylist[4]
                    }
                    self.dict[bot] = data                  
                    connection.join(mylist[0])
                    connection.privmsg(mylist[1], "xdcc send #%s" % mylist[2])
                    if "moviegods" in mylist[0]:
                        connection.join("#MG-CHAT")                    
                    log("Channel joined (%s) and package requested" % mylist[0]).write()
                    self.on_welcome(connection, event, first=False)                


    #added to request again if channel didn't load properly
    def retry_pack(self, connection, bot):
        while connection.connected and self.dict[bot]["down"]:
            try:
                print("nick: %s file: %s id: %d" % (bot,
                    self.dict[bot]["down"].filename, self.dict[bot]["down"].id))
                time.sleep(3)
            except Exception as e:
                print (e)


    def on_welcome(self, connection, event, first=True):
        if self.direct:
            self.dict[self.bot]["down"].status = "Waiting for direct file transfer"
            self.dict[self.bot]["down"].save()
            print("bot launched for direct file transfer")
        else:
            print("bot launched for %s" % self.bot)
            self.dict[self.bot]["down"].status, self.dict[self.bot]["down"].sizeraw = (
                "Waiting for package (in queue)...", self.dict[self.bot]["size"]) 
            self.dict[self.bot]["down"].save()
        s=threading.Timer(0, self.signal_listener, [connection, event])
        s.daemon=True
        s.start()
        if first and not self.direct:      
            connection.join(self.dict[self.bot]["channel"])
            #must join mg-chat channel to download on moviegods
            if "moviegods" in self.dict[self.bot]["channel"]:
                connection.join("#MG-CHAT")
                log("Channel #mg-chat joined to be able to download").write()
            connection.privmsg(self.bot, self.dict[self.bot]["msg"])
            log("Channel joined (%s) and package requested" % self.dict[self.bot]["channel"]).write()


    def on_kill(self, connection, event):
        log("booted").write


    def on_ctcp(self, c, e):
        print (e.arguments)
        if e.arguments[0] == "DCC":
            self.on_dccsend(c, e)
        else:
            bot = e.source.nick
            if e.arguments[0] == "VERSION":
                c.ctcp_reply(bot, "VERSION " + "Python irc.bot ({version})".format(
            version=irc.client.VERSION_STRING))

    def on_dccsend(self, c, e):
        bot = e.source.nick
        if self.direct:
            self.dict[bot] = self.dict.pop(self.bot)
            self.bot = bot
        #if the user cancels the download right away we're getting the DCC Send message, we'll still connect, which is bad, let's catch cancel
        if not self.dict[bot]["cancel"]:        
            downloads_dir = directory()
            if e.arguments[1].split(" ", 1)[0] == "SEND":
                proceed = True
                if self.direct:
                    dw = self.dict[bot]["down"]
                    main.queuedict[dw.server+self.bot] = main.queuedict.pop(dw.server+dw.username)
                    self.dict[bot]["down"].username = self.bot
                    self.dict[bot]["down"].save()
                    if e.arguments[1].split(" ")[5] == self.dict[bot]["pw"]:
                        print("password correct")
                    else:
                        #invalid password
                        print("bad password")
                        c.ctcp("CHAT", e.source.nick, "wrong password")
                        proceed = False                
                if proceed:
                    if '"' in e.arguments[1]:
                        #remove spaces from filename
                        one = e.arguments[1].find('"')
                        two = e.arguments[1].find('"', one + 1)
                        new = e.arguments[1][one+1:two].replace(" ", ".")
                        e.arguments[1] = e.arguments[1][:one] + new + e.arguments[1][two+1:]     
                    self.dict[bot]["filename"] = e.arguments[1].split(" ")[1]
                    self.port = int(e.arguments[1].split(" ")[3])
                    self.ip = irc.client.ip_numstr_to_quad(e.arguments[1].split(" ")[2])
                    try:
                        #update size; sometimes the given size (on the search engine) isnt the same as the sent size
                        self.dict[bot]["size"] = self.dict[bot]["down"].sizeraw = int(e.arguments[1].split(" ")[4])
                    except:
                        pass
                    if os.path.exists(os.path.join(downloads_dir, self.dict[bot]["filename"])):
                        print ("resuming download")
                        self.dict[bot]["position"] = os.path.getsize(os.path.join(downloads_dir, self.dict[bot]["filename"]))
                        c.ctcp("DCC", e.source.nick, "RESUME %s %d %d" % (self.dict[bot]["filename"], self.port, self.dict[bot]["position"]))      
                    else:
                        self.process(c, e)
            elif e.arguments[1].split(" ", 1)[0] == "ACCEPT":
                self.process(c, e, resume=True)

    def process(self, c, e, resume=False):
        #"When receiving a file with DCC, accept it"
        downloads_dir = directory()
        bot = e.source.nick
        try:
            connection = self.dcc_connect(self.ip, self.port, "raw")
        except irc.client.DCCConnectionError as e:
            log('Couldn\'t connect to DCC peer: %s' % e).write()
            self.dict[bot]["hist"].status, self.dict[bot]["hist"].time = "Peer connection error", utcnow()
            self.dict[bot]["hist"].save()            
            views.manage_queue(self.dict[bot]["down"])
            return ""
        if resume:
            self.dict[bot]["file"] = open(os.path.join(downloads_dir, self.dict[bot]["filename"]), 'ab')
            self.dict[bot]["down"].filename, self.dict[bot]["down"].status = (
                self.dict[bot]["filename"], "Resuming download...")
            log('Resuming download of %s' % self.dict[bot]["filename"]).write()
        else:
            self.dict[bot]["file"] = open(os.path.join(downloads_dir, self.dict[bot]["filename"]), 'wb')
            self.dict[bot]["down"].filename, self.dict[bot]["down"].status, self.dict[bot]["down"].sizeraw = (
                self.dict[bot]["filename"], "Starting download...", self.dict[bot]["size"])            
            log('Starting download of %s' % self.dict[bot]["filename"]).write()

        self.DCCconnections_dict[bot] = connection
        self.dict[bot]["hist"].time = utcnow()
        self.dict[bot]["down"].save()
        t = threading.Timer(0, monitoring, [self, connection, bot, int(self.dict[bot]["position"])])
        t.start()
        s=threading.Timer(0, self.retry_pack, [connection, bot])
        s.daemon=True
        s.start()



    def on_dccmsg(self, connection, event):
        #if dccmsg is raw data, nick is not sent, we need to retrieve it from our DCCconnections_dict
        for key, value in self.DCCconnections_dict.items():
            if value == connection:
                bot = key
                break
        data = event.arguments[0]
        self.dict[bot]["file"].write(data)
        sz = self.dict[bot]["received_bytes"]
        self.dict[bot]["received_bytes"] = self.dict[bot]["received_bytes"] + len(data)
        structured = struct.pack("!Q", self.dict[bot]["received_bytes"])
        try:
            connection.send_bytes(structured)
        except AttributeError:
            #in case the user pressed cancel, catch the 'NoneType' exception
            pass


    def on_dcc_disconnect(self, connection, event, bot=""):
        for key, value in self.DCCconnections_dict.items():
            if value == connection:
                bot = key
                break
        try:
            self.dict[bot]["file"].close()
        except:
            bot = bot
        if self.dict[bot]["stop"]:
            return ""        
        if self.dict[bot]["cancel"] == False:
            (self.dict[bot]["down"].status, self.dict[bot]["down"].progress, self.dict[bot]["down"].speed, 
                self.dict[bot]["down"].progress, self.dict[bot]["down"].eta) = "Extracting...", None, None, None, None
            self.dict[bot]["down"].save()
            tot = self.dict[bot]["received_bytes"]+self.dict[bot]["position"]
            log("Received file (%d bytes)." % tot  ).write()
            log("Size (%d bytes)." % int(self.dict[bot]["size"]) ).write()
            percdone = tot/int(self.dict[bot]["size"])
            duration = (utcnow() - self.dict[bot]["hist"].time)
            average = int(self.dict[bot]["size"])/1024/duration.total_seconds()
            (self.dict[bot]["hist"].filename, self.dict[bot]["hist"].status, self.dict[bot]["hist"].average, 
                self.dict[bot]["hist"].duration, self.dict[bot]["hist"].time, self.dict[bot]["hist"].sizeraw) = (self.dict[bot]["filename"],
                "Downloaded", round(average, 0), duration, utcnow(), self.dict[bot]["size"])
            self.dict[bot]["hist"].save()
            if os.path.exists(os.path.join(directory(), self.dict[bot]["filename"])):
                #added to prevent extracting incomplete files (internet connection interrupted)
                if percdone > 99/100:
                    untar(os.path.join(directory(), self.dict[bot]["filename"]), 
                        self.dict[bot]["filename"], self.dict[bot]["down"], self.dict[bot]["hist"])
                    return ""
            
            self.dict[bot]["down"].status = "Error during file transfer"
            self.dict[bot]["down"].save()
            self.dict[bot]["hist"].status, self.dict[bot]["hist"].time = "Error during file transfer", utcnow()
            self.dict[bot]["hist"].save()
            log("Error during file transfer. Completed percentage: %d" % int(percdone*100) ).write()
            print ("2")
            views.manage_queue(self.dict[bot]["down"])
            return ""
        else:
            self.dict[bot]["cancel"] = False
            views.manage_queue(self.dict[bot]["down"])
            return ""



    def on_disconnect(self, connection, event):
        print ("disconnected")
        log("disconnected").write()


    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")
        log("Nickname already used. Now using %s" % (c.get_nickname() + "_")).write()

    def on_privnotice(self, c, e):
        bot = e.source.nick
        a = e.arguments[0].split(":", 1)
        log(a).write()
        if "invalid pack number" in str(a).lower():
            self.DCCconnections_dict[bot].disconnect()
            self.dict[bot]["hist"].status, self.dict[bot]["hist"].time = "Dead link from the search engine", utcnow()
            self.dict[bot]["down"].status, self.dict[bot]["down"].active = "Invalid pack number", False
            self.dict[bot]["down"].save()
            self.dict[bot]["hist"].save()            
            log("Discarding download due to invalid pack number, proceeding to next item in queue if existing.").write()
            print ("3")
            views.manage_queue(self.dict[bot]["down"])

    def on_dccchat(self, c, e):
        log("dccchat").write()
        if len(e.arguments) != 2:
            return
        args = e.arguments[1].split()
        if len(args) == 4:
            try:
                address = ip_numstr_to_quad(args[2])
                port = int(args[3])
            except ValueError:
                return
            self.dcc_connect(address, port)


def DCC_deamonthread(c, server, nickname, hist, down, size=0):
    """
    If a server connection fails, there is no point in checking the queue for further downloads;
    There, we try to reconnect as soon as the connection timed out.
    To be able to interrupt the connection attempt loop, we use the signal listener and pass the server connection
    """
    botqueue = main.queuedict[server+c.bot] = Queue()
    i=1    
    while True:
        try:
            c.connect(server, 6667, nickname)
            c.start()
            break
        except irc.client.ServerConnectionError as x:
            log("error (%s)" % i + str(x)).write()
            hist.status, hist.time, hist.sizeraw = "Error during connection (%d)" % i, utcnow(), size
            hist.save()
            down.status = "Connecting to server... (%d)" % (i+1)
            down.save()
            i+=1
            if not botqueue.empty():
                mystring = botqueue.get()
                if "cancel" in mystring:
                    views.manage_queue(down)
                    break
 

    
def xdcc(resume=False, **kwargs):
    """
    when this function is called, every check has been made and the download has to be launched;
    a new bot has to be created as well as a new Download_Ongoing item;
    One bot corresponds to one server connection instance;
    One bot can have multiple DCC connections, thus handling multiple downloads    
    the History item is created for easy access, but saved only when download is finished, e.g
    completed/interrupted/canceled
    """
    down = hist = None #these are the two database objects
    irc.client.ServerConnection.buffer_class.encoding = 'latin-1'
    if resume:
        #resume = True
        log("Resume = True").write()
        down = kwargs["down_obj"]
        down.status, down.active ="Connecting to server...", True
        try:
            hist = Download_History.objects.filter(down.server).latest("id")
            if hist.attempts:
                hist.attempts+=1
        except:
            hist = Download_History(filename=kwargs["filename"]) 
    if not "filename" in kwargs:
        #direct file transfer between two IRCapp users
        server = "irc.rizon.net"# I know, pretty arbitrary, we'll make this configurable in a future version (config.ini probably)
        nickname = kwargs["nick"]
        down = Download_Ongoing(filename="Direct file transfer enabled", 
            server=server, username=nickname, status="Connecting to server...", active=False)
        hist = Download_History()  
        log("Direct = True").write()
        c = DCCReceive(direct=True, nickname=nickname, password=kwargs["pw"], down=down, hist=hist)
        t = threading.Thread(target=DCC_deamonthread, args=(c, server, nickname, hist, down))
    else:
        if not resume:
            #regular download, create new database objects
            down = Download_Ongoing(filename=kwargs["filename"], status="Connecting to server...", active=True)
            hist = Download_History(filename=kwargs["filename"])    
        size, server, channel, xdccbot, xdccrequest = (kwargs["size"], kwargs["server"],
            kwargs["channel"], kwargs["username"], kwargs["package_number"])
        msg = "xdcc send #%s" % xdccrequest
        down.server, down.channel, down.username, down.package_number = server, channel, xdccbot, xdccrequest
        c = DCCReceive(bot=xdccbot, msg=msg, channel=channel, size=size, filename=kwargs["filename"], down=down, hist=hist)        
        #anonymous nickname
        nickname = ''.join(random.choice(string.ascii_lowercase) for i in range(8))
        t = threading.Thread(target=DCC_deamonthread, args=(c, server, nickname, hist, down, size))
    down.save()
    t.daemon=True
    t.start()




def splitext(path):
    for ext in ['.tar.gz', '.tar.bz2']:
        if path.endswith(ext):
            return path[:-len(ext)], path[-len(ext):]
    return os.path.splitext(path)

def untar(completefile, filename, down, hist):
    log("Extracting the file...").write()
    log(completefile + ' ' + filename).write()
    # tar file to extract
    theTarFile = completefile

    # tar file path to extract
    extractTarPath = os.path.join(directory(), '_UNPACK_' + splitext(filename)[0])
    if tarfile.is_tarfile(theTarFile):
        # extract all contents
        try:
            tfile = tarfile.open(theTarFile)
            tfile.extractall(extractTarPath)
            tfile.close()
            os.remove(theTarFile)
            #extract rar files
            x=0
            completefile = False
            #this test is added in case some txt is extracted with the folder
            while not os.path.isdir(os.path.join(extractTarPath, os.listdir(extractTarPath)[x])):
                #sometimes the file extracted is the final file, no futher rar extraction needed; in this case, test for it's size and finish
                if os.path.getsize(os.path.join(extractTarPath, os.listdir(extractTarPath)[x])) > 90/100*hist.sizeraw:
                    completefile = True
                    break
                x+=1
            if not completefile:
                origin = os.path.join(extractTarPath, os.listdir(extractTarPath)[x])
                log(origin).write()
                for fl in os.listdir(origin):
                    shutil.move(os.path.join(origin, fl), extractTarPath)
                shutil.rmtree(origin)
                for archivefile in os.listdir(extractTarPath):
                    if ".rar" in archivefile:
                        arch_ref = rarfile.RarFile(os.path.join(extractTarPath, archivefile),'r')
                        arch_ref.extractall(extractTarPath)
                #remove rest
                for fl in os.listdir(extractTarPath):
                    ext = splitext(fl)[1].lower()
                    pathToDelete = os.path.join(extractTarPath, fl)
                    if os.path.isdir(pathToDelete):
                    # Do not delete non-empty dirs, could contain useful files.
                        try:
                            os.rmdir(pathToDelete);
                        except OSError as ex:
                            if ex.errno == errno.ENOTEMPTY:
                                log("Did not delete non-empty directory : %s" %  pathToDelete).write()
                            else:
                                log("An error occurred deleting directory : %s" % pathToDelete).write()
                    else:
                        if ext[:2] == '.r' or ext in ['.sfv', '.nfo', '.png', '.jpg'] or 'sample' in fl:
                            os.remove(os.path.join(extractTarPath, fl))
            #remove UNPACK from name when done
            os.rename(extractTarPath, os.path.join(directory(), splitext(filename)[0]))
        except Exception as e:
            log("An error occured during file extraction : %s" % e).write()
            hist.status, hist.time = "Error during file extraction", utcnow()
            down.status, down.sizeraw, down.active = "Error during file extraction", None, False
            down.save()
            hist.save()
            print ("4")
            views.manage_queue(down)
            return ""

    else:
        log(theTarFile + " is not a tarfile.").write()


    down.status, down.sizeraw, down.active = "Downloaded and extracted properly", None, False
    hist.status, hist.time = "Downloaded and extracted properly", utcnow()
    hist.save()
    down.save()
    print ("5")
    views.manage_queue(down)
    return ""

#if __name__ == "__main__":
#    xdcc(data, filename)
