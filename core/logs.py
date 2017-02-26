import datetime
import os, sys
from core.models import Download_Path
import settings

def directory():
    if Download_Path.objects.all().count() == 0:
        #temporary solution to get download path for english, german and french speaking users to avoid third party dependancy
        default = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(default):
            default = os.path.join(os.path.expanduser('~'), 'Téléchargements')  
        #config.ini file has priority
        with open(os.path.join(settings.BASE_DIR, "config.ini"), "r") as cfg:
            content = cfg.readlines()
            path = content[4][1+content[4].index("="):content[4].index("#")].strip(" ")
            cfg.close()
        if path:
            default = path
        if os.path.exists(default):
            Download_Path(download_path=default).save()
            return Download_Path.objects.latest('id').download_path
        else:
            return "Error : could not find default download directory"
    else:
        return Download_Path.objects.latest('id').download_path
            
class log:
    def __init__(self, txt=""):        
        self.text = str(txt)
        if sys.platform == "win32":
            self.my_log = os.path.join(os.environ["LOCALAPPDATA"], "IRCapp", "log.txt")
        else:
            self.my_log = os.path.join(os.path.expanduser("~"), ".IRCapp", "log.txt")               
   
    def write(self):        
        with open(self.my_log, "a") as txtf:
            txtf.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + " : " + self.text + "\n")
            txtf.close()
    def clear(self):
        with open(self.my_log, "w") as txtf:
            txtf.write("")
            txtf.close()

