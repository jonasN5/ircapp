import datetime
from django.utils.translation import ugettext as _
import os, sys
from ircapp.models import Download_Path

def directory():
    if Download_Path.objects.all().count() == 0:
        default = os.path.join(os.path.expanduser('~'), _('Downloads'))
        if not os.path.exists(default):
            default = os.path.join(os.path.expanduser('~'), _('Téléchargements'))
        if os.path.exists(default):
            Download_Path(download_path=default).save()
            return Download_Path.objects.latest('id').download_path
        else:
            return _("Error : could not find default download directory")
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

