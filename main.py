import os, sys
import webbrowser
import threading
import time
import requests
import django
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application 
import cherrypy
from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
from core.models import *
from core.download import *
from core.forms import *
from core.logs import *
import views
queuedict = {}

HOST = "127.0.0.1"
PORT = 8020

 
class IRCapp(object):

    def open_browser(self):
        while True:
            try:
                c = requests.get('http://' + HOST + ':' +  str(PORT) + '/')
                if c.status_code == 200:
                    webbrowser.open('http://' + HOST + ':' +  str(PORT) + '/')
                    break
            except Exception as e:
                time.sleep(0.2)     
        
    def mount_static(self, url, root):
        """
        :param url: Relative url
        :param root: Path to static files root
        """
        config = {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': root,
            'tools.expires.on': True,
            'tools.expires.secs': 86400
        }
        cherrypy.tree.mount(None, url, {'/': config})

    def run(self):
        cherrypy.config.update({
            'server.socket_host': HOST,
            'server.socket_port': PORT,
            'engine.autoreload.on': False,
            'log.screen': True
        })
        self.mount_static(settings.STATIC_URL, settings.STATIC_ROOT)
        #cherrypy.process.plugins.PIDFile(cherrypy.engine, os.path.join(settings.BASE_DIR, 'IRCapp.pid')).subscribe()
        cherrypy.log("Loading and serving IRCapp")
        cherrypy.tree.graft(WSGIHandler())
        cherrypy.engine.start()
        
        obj = Download_Settings.objects.latest('id')
        if not obj.restart:
            t = threading.Thread(target=self.open_browser())
            t.deamon = True
            t.start()
        else:
            obj.restart = False
            obj.save()       

        cherrypy.engine.block()

def start_ircapp():            
    #update HOST and PORT with config.ini specifications
    with open(os.path.join(settings.BASE_DIR, "config.ini"), "r") as cfg:
        global HOST, PORT
        content = cfg.readlines()
        HOST = content[0][1+content[0].index("="):content[0].index("#")].strip(" ")
        PORT = int(content[1][1+content[1].index("="):content[1].index("#")].strip(" ")) 
        cfg.close()
    
    #check if application is already running : open browser   
    try:
        c = requests.get('http://' + HOST + ':' +  str(PORT) + '/')
        if c.status_code == 200:
            webbrowser.open_new_tab('http://' + HOST + ':' +  str(PORT) + '/')
            return
    except Exception as e:
        pass
    
    #launch IRCapp    
    application = get_wsgi_application()    
    if sys.platform == "win32":
        if not os.path.isdir(os.path.join(os.environ["LOCALAPPDATA"], "IRCapp")):
            os.makedirs(os.path.join(os.environ["LOCALAPPDATA"], "IRCapp"))
    else:
        if not os.path.isdir(os.path.join(os.path.expanduser("~"), ".IRCapp")):
            os.makedirs(os.path.join(os.path.expanduser("~"), ".IRCapp"))     
            
    log().clear()


    try:
        obj = Download_Settings.objects.latest('id')
    except:
        call_command('migrate', verbosity=0)#displaying stdout will result into an error in a GUI frozen application with cx freeze
        Download_Settings().save()
    finally:
        Upload_Ongoing.objects.all().delete()
        checklist=[]
        if Download_Ongoing.objects.all().count() > 0:        
            if not Download_Ongoing.objects.filter(active=True):
                Download_Ongoing.objects.all().delete()
            else:
                #case where we resume interrupted downloads
                for down_obj in Download_Ongoing.objects.all():
                    if not down_obj.active:
                        down_obj.delete()
                    else:
                        down_obj.status,  down_obj.speed, down_obj.eta, down_obj.tm = "Interrupted", None, None, None
                        down_obj.save()
                        checklist.append(down_obj.server)
                        views.initial_download(down_obj)
        #in case there is a queue, let's check and launch
        if Download_Queue.objects.all().count() > 0:
            for queue_obj in Download_Queue.objects.all():
                if not queue_obj.server in checklist:
                    views.initial_download(queue_obj, what="queue")
                    checklist.append(queue_obj.server)
                    queue_obj.delete()              
                
        if Quick_Download.objects.all().count() == 0:
            Quick_Download().save()
        if Quick_Download_Excludes.objects.all().count() == 0:        
            Quick_Download_Excludes(excludes="hdts").save()
            Quick_Download_Excludes(excludes="hd-ts").save()
            Quick_Download_Excludes(excludes="cam").save()

    
    IRCapp().run() 

if __name__ == '__main__':
    start_ircapp()
