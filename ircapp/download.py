#!/usr/bin/python3



import sys, json
import os
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
from ircapp.logs import directory, log
from ircapp.models import *
import random, string
from django.utils.timezone import now as utcnow
import subprocess
import cherrypy

#these are the two global variables that will store History and Download_ongoing objects
global down, hist
down = None
hist = None


def monitoring(self, connection, position=0):
    sz = 0
    log("Monitoring started").write()
    while connection.connected:
        percentage = int(position + self.received_bytes) / int(self.size) * 100
        completed = int(position + self.received_bytes)
        speed = (self.received_bytes-sz)
        if speed != 0:
            tm = (int(self.size)-int(self.received_bytes)-position) / speed
        else:
            tm = 99999
        eta = utcnow() + datetime.timedelta(seconds=tm)

        speed = int(speed/1024)
        down.status, down.progress, down.completed, down.eta, down.timeleft = 'Downloading...', percentage, completed, eta, tm
        #workaround for occasionnal empty packages
        if speed:
            down.speed = speed
        down.save()

        sz = self.received_bytes
        if percentage >=100:
            self.reactor.disconnect_all()
            return ""
        time.sleep(1)
    log("Monitoring stoped").write()


#class Task(threading.Thread, dccobject):
#    dccobject.cancel()
    
class DCCReceive(irc.client.SimpleIRCClient):

    def __init__(self, bot, msg, channel, size, filename):
        irc.client.SimpleIRCClient.__init__(self)
        self.received_bytes = 0
        self.bot = bot
        self.msg = msg
        self.channel = channel
        self.size = size
        self.filename = filename
        self.hist = hist
        self.cancel = False
        self.position = 0
        self.queued = False

    def stop(self, connection):
        while Download_Ongoing.objects.get(id=down.id).active == True:
            time.sleep(0.5)
        if Download_Ongoing.objects.get(id=down.id).status == "Replaced into queue":
            log("Download not starting immediately, appending item to the download queue").write()
        elif Download_Ongoing.objects.get(id=down.id).status == "Canceled":
            log("Download canceled by the user").write()
        elif Download_Ongoing.objects.get(id=down.id).status == "Shutdown":
            log("Download interrupted by a user shutdown/restart").write()
        self.cancel = True
        if connection.connected and self.queued:
            # We don't want to leave dangling queues on cancellation.
            self.queued = False
            log("Removing from XDCC queue").write()
            connection.privmsg(self.bot, "XDCC REMOVE")
        self.reactor.disconnect_all()
        return ""


    #added to request again if channel didn't load properly
    def retry_pack(self, connection):
        if self.received_bytes == 0:
            if connection.connected:
                if self.queued:
                    log("Waiting in XDCC bot's queue").write()
                else:
                    connection.privmsg(self.bot, self.msg)
                    log("Package requested again").write()

    def on_welcome(self, connection, event):
        connection.join(self.channel)
        #must join mg-chat channel to download on moviegods
        if "#moviegods" in self.channel:
            connection.join("#mg-chat")
            log("Channel #mg-chat joined to be able to download").write()
        connection.privmsg(self.bot, self.msg)
        log("Channel joined (%s) and package requested" % self.channel).write()
        down.status, down.sizeraw = "Waiting for package (in IRCapp queue)...", self.size
        down.save()
        s=threading.Timer(60.0, self.retry_pack, [connection])
        s.daemon=True
        s.start()

        s=threading.Timer(0, self.stop, [connection])
        s.daemon=True
        s.start()




    def on_kill(self, connection, event):
        log("booted").write


    def on_ctcp(self, c, e):
        #"Deal with CTCP..."
        if e.arguments[0] == "DCC":
            self.on_dccsend(c, e)
        else:
            nick = e.source.nick
            if e.arguments[0] == "VERSION":
                c.ctcp_reply(nick, "VERSION " + "Python irc.bot ({version})".format(
            version=irc.client.VERSION_STRING))

    def on_dccsend(self, c, e):
        downloads_dir = directory()
        if e.arguments[1].split(" ", 1)[0] == "SEND":
            self.filename = e.arguments[1].split(" ")[1]

            self.port = int(e.arguments[1].split(" ")[3])
            self.ip = irc.client.ip_numstr_to_quad(e.arguments[1].split(" ")[2])
            try:
                #update size; sometimes the given size (on the search engine) isnt the same as the sent size
                self.size = int(e.arguments[1].split(" ")[4])
            except:
                pass
            if os.path.exists(os.path.join(downloads_dir, self.filename)):
                self.position = os.path.getsize(os.path.join(downloads_dir, self.filename))
                c.ctcp_reply(e.source.nick, "DCC RESUME"+" "+ self.filename + " " + str(self.port) + " " + str(self.position))
            else:
                self.process(c, e)
        elif e.arguments[1].split(" ", 1)[0] == "ACCEPT":
            self.process(c, e, resume=True)

    def process(self, c, e, resume=False):
        #"When receiving a file with DCC, accept it"
        downloads_dir = directory()
        # No longer queued, if download stalls here it's an actual problem.
        self.queued = False

        if resume:
            self.file = open(os.path.join(downloads_dir, self.filename), 'ab')
            down.filename, down.status, down.sizeraw = self.filename, "Resuming download...", self.size
            log('Resuming download of %s' % self.filename).write()
        else:
            self.file = open(os.path.join(downloads_dir, self.filename), 'wb')
            down.filename, down.status, down.sizeraw = self.filename, "Starting download...", self.size
            log('Starting download of %s' % self.filename).write()

        connection = self.dcc_connect(self.ip, self.port, "raw")
        hist.time = utcnow()
        down.save()
        #monitor().write(filename=self.filename, status="Starting download...")
        t = threading.Timer(0, monitoring, [self, connection, int(self.position)])
        t.start()


    def on_dccmsg(self, connection, event):
        data = event.arguments[0]
        self.file.write(data)
        sz = self.received_bytes
        self.received_bytes = self.received_bytes + len(data)
        structured = struct.pack("!Q", self.received_bytes)
        connection.send_bytes(structured)


    def on_dcc_disconnect(self, connection, event):
        self.file.close()
        try:
            self.connection.quit()
        except:
            pass
        if self.cancel == False:
            down.status, down.progress, down.speed, down.progress, down.eta = "Extracting...", None, None, None, None
            down.save()
            tot = self.received_bytes+self.position

            log("Received file (%d bytes)." % tot  ).write()
            log("Size (%d bytes)." % int(self.size) ).write()
            percdone = (tot)/int(self.size)
            duration = (utcnow() - self.hist.time)
            average = int(self.size)/1024/duration.total_seconds()
            hist.filename, hist.status, hist.average, hist.duration, hist.time, hist.sizeraw = self.filename, "Downloaded", round(average, 0), duration, utcnow(), self.size
            hist.save()
            if os.path.exists(os.path.join(directory(), self.filename)):
                #add to prevent extracting incomplete files (internet connection interrupted)
                if percdone > 99/100:
                    #self.connection.quit()
                    untar(os.path.join(directory(), self.filename), self.filename)


                    return ""
            hist.status, hist.time = "Error during file transfer", utcnow()
            down.status, down.sizeraw, down.active = "Error during file transfer", None, False
            down.save()
            hist.save()
            log("Error during file transfer. Completed percentage: %d" % percdone ).write()
            return ""






    def on_disconnect(self, connection, event):

        log("disconnected").write()


    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")
        log("Nickname already used. Now using %s" % (c.get_nickname() + "_")).write()

    def on_privnotice(self, c, e):
        a = e.arguments[0].split(":", 1)
        log(a).write()
        if "invalid pack number" in str(a).lower():
            self.connection.quit()

            self.hist.status, self.hist.time = "Dead link from the search engine", utcnow()
            down.status, down.active = "Invalid pack number", False
            down.save()
            self.hist.save()

            log("Discarding download due to invalid pack number, proceeding to next item in queue if existing.").write()
        if "all slots full" in str(a).lower():
            self.queued = True
            log("Added to XDCC bot's queue").write()
            down.status = "Waiting for package (in XDCC bot queue)..."
            down.save()

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

    def do_command(self, e, cmd):
        nick = e.source.nick
        c = self.connection

        if cmd == "disconnect":
            self.disconnect()
        elif cmd == "die":
            self.die()
        elif cmd == "stats":
            for chname, chobj in self.channels.items():
                c.notice(nick, "--- Channel statistics ---")
                c.notice(nick, "Channel: " + chname)
                users = sorted(chobj.users())
                c.notice(nick, "Users: " + ", ".join(users))
                opers = sorted(chobj.opers())
                c.notice(nick, "Opers: " + ", ".join(opers))
                voiced = sorted(chobj.voiced())
                c.notice(nick, "Voiced: " + ", ".join(voiced))
        elif cmd == "dcc":
            dcc = self.dcc_listen()
            c.ctcp("DCC", nick, "CHAT chat %s %d" % (
                ip_quad_to_numstr(dcc.localaddress),
                dcc.localport))
        else:
            c.notice(nick, "Not understood: " + cmd)

def DCC_deamonthread(c, server, nickname, hist, down):
    try:
        c.connect(server, 6667, nickname)
        c.start()
    # On Mac OS irc's process_once() seems to throw OSError: [Errno 9] Bad file descriptor
    # during disconnect, we can just suppress the error here but we should log.
    except (irc.client.ServerConnectionError, OSError) as x:
        log("error" + str(x)).write()
        hist.status, hist.time, hist.sizeraw = "Error during connection", utcnow(), size
        hist.save()
        down.status, down.active = "Error during connection", False
        down.save()
    
def xdcc(data, filename="", resume=False):
    global hist, down
    log(data).write()
    if resume:
        #global hist, down
        down = Download_Ongoing.objects.latest("id")
        down.status, down.active ="Connecting to server...", True
        try:
            hist = Download_History.objects.latest("id")
            if hist.attempts:
                hist.attempts+=1
        except:
            hist = Download_History(filename=filename)
    else:
        #global hist, down
        Download_Ongoing.objects.all().delete()
        down = Download_Ongoing(filename=filename,status="Connecting to server...", active=True)
        hist = Download_History(filename=filename)
    down.save()
    size, server, channel, xdccbot, xdccrequest = data.split(",")
    msg = "xdcc send #%s" % xdccrequest
    irc.client.ServerConnection.buffer_class = irc.buffer.LenientDecodingLineBuffer
    c = DCCReceive(xdccbot, msg, channel, size, filename)
    #anonymous nickname
    nickname = ''.join(random.choice(string.ascii_lowercase) for i in range(8))

    t = threading.Thread(target=DCC_deamonthread, args=(c, server, nickname, hist, down))
    t.daemon=True
    t.start()
    #factory = Factory(bind_address=(os.environ['OPENSHIFT_PYTHON_IP'], 0))



def splitext(path):
    for ext in ['.tar.gz', '.tar.bz2']:
        if path.endswith(ext):
            return path[:-len(ext)], path[-len(ext):]
    return os.path.splitext(path)

def untar(completefile, filename):
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
                    if os.path.isdir(os.path.join(extractTarPath, fl)):
                        shutil.rmtree(os.path.join(extractTarPath, fl))
                    else:
                        if ext[:2] == '.r' or ext == '.sfv' or ext == '.nfo' or 'sample' in fl:
                            os.remove(os.path.join(extractTarPath, fl))
            #remove UNPACK from name when done
            os.rename(extractTarPath, os.path.join(directory(), splitext(filename)[0]))
        except Exception as e:
            log("An error occured during file extraction : %s" % e).write()
            hist.status, hist.time = "Error during file extraction", utcnow()
            down.status, down.sizeraw, down.active = "Error during file extraction", None, False
            down.save()
            hist.save()
            return ""

    else:
        log(theTarFile + " is not a tarfile.").write()


    down.status, down.sizeraw, down.active = "Downloaded and extracted properly", None, False
    hist.status, hist.time = "Downloaded and extracted properly", utcnow()
    hist.save()
    down.save()
    return ""

#if __name__ == "__main__":
#    xdcc(data, filename)
