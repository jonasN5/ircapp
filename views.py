from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.core import serializers
from ircapp.logs import directory, log
from ircapp.download import xdcc
from ircapp.models import *
from ircapp.forms import *
import requests
import sys, json
import base64
import threading
import ctypes
import os, subprocess
import platform
import time
import settings
import datetime
from django.utils.timezone import localtime
from django.utils.timezone import now as utcnow
import cherrypy


def get_free_space_mb():
    """Return folder/drive free space (in megabytes)."""
    dirname = directory()
    if os.path.exists(dirname):
        if platform.system() == 'Windows':
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(dirname), None, None, ctypes.pointer(free_bytes))
            return round(free_bytes.value / (1024**3), 2)
        else:
            st = os.statvfs(dirname)
            return round(st.f_bavail * st.f_frsize / (1024**3), 2)
    else:
        return -1

def space(request):
    space = get_free_space_mb()
    return JsonResponse({ 'space' : space }, safe=False)

def download_path(request):
    if Download_Path.objects.all().count() == 0:
        path_form = PathForm(data=request.POST)
    else:
        path_form = PathForm(data=request.POST, instance=Download_Path.objects.latest('id'))
    if path_form.is_valid():
        path_form.save()
        return JsonResponse({ 'msg' : "Path is valid and has been saved", }, safe=False)
    else:
        return JsonResponse({ 'msg' : path_form['download_path'].errors, }, safe=False)

'''
Externalized to sourceforge.net

def report_bug(request):
    if not "Ircapp" in os.path.dirname(sys.executable):
        attachment="log.txt"
    else:
        attachment=os.path.join(os.path.dirname(sys.executable), "log.txt")
    body="Please describe your bug shortly with the circumstances in which it happened"
    mails=settings.ADMINS
    #mails="ircappwebmaster@gmail.com"
    mailto.main(address=mails, mailto_mode=True, subject="IRCapp bug report", body=body, attach=attachment)
    return HttpResponse("")
'''

def splitext(path):
    for ext in ['.tar.gz', '.tar.bz2']:
        if path.endswith(ext):
            return path[:-len(ext)], path[-len(ext):]
    return os.path.splitext(path)

def opendir(request):
    pk = int(request.GET['pk'])
    try:
        basefolder = Download_Path.objects.latest('id').download_path
        foldername = basefolder
        if pk != 0:
            fileobject = Download_History.objects.get(pk=pk)
            if "extracted" in fileobject.status and ".tar" in splitext(fileobject.filename)[1]:
                foldername = os.path.join(basefolder, splitext(fileobject.filename)[0])
        else:
            fileobject = Download_Ongoing.objects.latest('id')
            if "Extracting" in fileobject.status and ".tar" in splitext(fileobject.filename)[1]:
                foldername = os.path.join(basefolder, '_UNPACK_' + splitext(fileobject.filename)[0])
            elif "extracted" in fileobject.status and ".tar" in splitext(fileobject.filename)[1]:
                foldername = os.path.join(basefolder, splitext(fileobject.filename)[0])
        if sys.platform == "win32":
            os.startfile(foldername)
        else:
            opener ="open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, foldername])
        return HttpResponse("")
    except Exception as e:
        return HttpResponse("Error: %s" % e)

def preferences(request):
    if request.method == "POST":
        try:
            body = request.POST['contains']
            resp = Quick_Download_Contains(contains=body)
            resp.save()
            return JsonResponse({ 'id' : resp.id, 'text' : resp.contains}, safe=False)
        except: pass
        try:
            body = request.POST['excludes']
            resp = Quick_Download_Excludes(excludes=body)
            resp.save()
            return JsonResponse({ 'id' : resp.id, 'text' : resp.excludes}, safe=False)
        except:
            body = request.POST['priority']
            Quick_Download(id=Quick_Download.objects.latest('id').id, priority=body).save()
            return HttpResponse("")

def delete_pref(request):
    pk = request.GET['pk']
    try:
        contain = request.GET['contains']
        Quick_Download_Contains.objects.get(pk=pk).delete()
        return HttpResponse("")
    except:
        exclude = request.GET['excludes']
        Quick_Download_Excludes.objects.get(pk=pk).delete()
        return HttpResponse("")

def read_log(request):
    log_file = open(log().my_log)
    response = HttpResponse(content=log_file)
    response['Content-Type'] = 'text/plain'
    return response
    
def index(request):

    downbox = Download_Settings.objects.latest('id').download_box
    quickdown_value = Quick_Download.objects.latest('id').priority
    contain=[]
    if Quick_Download_Contains.objects.all():
        for x in Quick_Download_Contains.objects.all():
            contains={}
            contains['id'] = x.id
            contains['text'] = x.contains
            contain.append(contains)
    exclude=[]
    if Quick_Download_Excludes.objects.all():
        for x in Quick_Download_Excludes.objects.all():
            excludes = {}
            excludes['id'] = x.id
            excludes['text'] = x.excludes
            exclude.append(excludes)
    try:
        pathinstance = Download_Path.objects.latest('id')
        pathform = PathForm(instance=pathinstance)
    except:
        pathform = PathForm()
    context = {
        'directory' : directory(),
        'free_space' : get_free_space_mb(),
        'pathform' : pathform,
        'quickdown_value' : quickdown_value,
        'contains' : contain,
        'excludes' : exclude,
        'pathform' : pathform,
        'downbox' : downbox,
    }
    return render(request, 'search.html', context)


def quick_download(request):
    q = request.GET['q']
    data = quickinfo(q)
    Quick = True
    if data == "":
            Quick = False
    if Quick:
        '''
        quick download enabled : download without displaying results
        ajax call with jQuery
        '''
        server = data["naddr"]
        channel = data["cname"]
        xdccbot = data["uname"]
        xdccrequest = data["n"]
        sizeraw = int(data["sz"])
        size = format_number(sizeraw)
        name = data["name"]
        data = str(sizeraw)+","+server+","+channel+","+xdccbot+","+str(xdccrequest)
        if Download_Ongoing.objects.all().count() > 0 or get_free_space_mb() <= sizeraw/(1024**3):
            if get_free_space_mb() <= sizeraw/(1024**3) or Download_Ongoing.objects.latest("id").active:
                #download in progress or not enough disk space, adding to queue
                queue = Download_Queue(title=name, sizeraw=sizeraw, network=server, channel=channel, username=xdccbot, number=xdccrequest)
                queue.save()
                queue = prepare(Download_Queue.objects.latest("id"))
                return JsonResponse(queue, safe=False)
        #no download in progress
        #Create a backup object to be able to resume download
        Resume_Backup.objects.all().delete()
        Resume_Backup(title=name, sizeraw=sizeraw, network=server, channel=channel, username=xdccbot, number=xdccrequest, attempts=1).save()
        #launch download
        xdcc(data, name)
        hist = prepare(Download_History.objects.latest("id"))
        return JsonResponse(hist, safe=False)
    else:
        '''
        no match found with quick download method
        display search results instead
        '''
        return JsonResponse({ 'redirect' : True, 'q' : q }, safe=False)

def search_download(request):
    name = request.GET['filename']
    data = request.GET['data']
    sizeraw, server, channel, xdccbot, xdccrequest = data.split(",")[0:]
    if Download_Ongoing.objects.all().count() > 0 or get_free_space_mb() <= int(sizeraw)/(1024**3):
        if get_free_space_mb() <= int(sizeraw)/(1024**3) or Download_Ongoing.objects.latest("id").active:
            #download in progress or not enough disk space, adding to queue
            queue = Download_Queue(title=name, sizeraw=int(sizeraw), network=server, channel=channel, username=xdccbot, number=xdccrequest)
            queue.save()
            queue = prepare(Download_Queue.objects.latest("id"))
            queue["type"] = "queue"
            return JsonResponse(queue, safe=False)
    #no download in progress
    #Create a backup object to be able to resume download

    Resume_Backup(title=name, sizeraw=int(sizeraw), network=server, channel=channel, username=xdccbot, number=xdccrequest, attempts=1).save()
    #launch download
    xdcc(data, name)
    hist = prepare(Download_History.objects.latest("id"))
    hist["type"] = "history"
    return JsonResponse(hist, safe=False)


def queue_download(request):
    resume = None
    try:
        resume = request.GET['resume']
        down = Resume_Backup.objects.latest("id")
        down.attempts+=1
        down.save()
    except:
        pk = request.GET['pk']
        down = Download_Queue.objects.get(pk=pk)
    server = down.network
    channel = down.channel
    xdccbot = down.username
    xdccrequest = down.number
    size = down.sizeraw
    filename = down.title
    #if not resuming download : remove item from queue imediately and create a copy as backup to be able to resume download
    if not resume:
        Download_Queue.objects.get(pk=pk).delete()
        Resume_Backup.objects.all().delete()
        Resume_Backup(title=filename, sizeraw=size, network=server, channel=channel, username=xdccbot, number=xdccrequest, attempts=1).save()
    #launch download
    data = str(size)+","+server+","+channel+","+xdccbot+","+str(xdccrequest)
    if resume:
        xdcc(data, filename, resume=True)
    else:
        xdcc(data, filename)
    hist = prepare(Download_History.objects.latest("id"))
    return JsonResponse(hist, safe=False)


def format_number(number, num_format="MB"):
    if num_format == "kB":
        return str(int(number/1024)) + " " + num_format
    elif num_format == "MB":
        return str(int(number/(1024**2))) + " " + num_format
    else:
        return str(round(number/(1024**3), 2)) + " " + num_format



def prep_history(download_object):
    raw = serializers.serialize('json', Download_History.objects.filter(pk=download_object.id))
    raw = json.loads(raw)
    raw = raw[0]
    try:
        if localtime(download_object.time).date() == utcnow().date():
            raw['fields']['time'] = localtime(download_object.time).time().strftime('%H:%M:%S')
        elif localtime(download_object.time).year == utcnow().year:
            raw['fields']['time'] = localtime(download_object.time).strftime('%d %b %H:%M:%S')
        else:
            raw['fields']['time'] = localtime(download_object.time).strftime('%Y %d %b %H:%M:%S')
    except :
        #time == None, do nothing
        pass
    try:
        s = download_object.duration.total_seconds()
        if s < 60:
            raw['fields']['duration'] = str(int(s)) + 's'
        elif s < 3600:
            raw['fields']['duration'] = str(int(s/60)) + 'm' + str(int(s%60)) + 's'
        else:
            raw['fields']['duration'] = str(int(s/3600)) + 'h' + str(int(s%3600/60)) + 'm' + str(int(s%3600%60)) + 's'
    except :
        #duration == None, do nothing
        pass
    del raw['model']
    try:
        if download_object.sizeraw/(1024**2) >= 1000:
            raw['fields']['size'] = format_number(download_object.sizeraw, "GB")
        else:
            raw['fields']['size'] = format_number(download_object.sizeraw)
    except :
        #duration == None, do nothing
        pass
    return raw

def prep_queue(download_object):
    #push formated size in json response
    raw = serializers.serialize('json', Download_Queue.objects.filter(pk=download_object.id))
    raw = json.loads(raw)
    raw = raw[0]
    if download_object.sizeraw/(1024**2) >= 1000:
        raw['fields']['size'] = format_number(download_object.sizeraw, "GB")
    else:
        raw['fields']['size'] = format_number(download_object.sizeraw)
    del raw['model']
    return raw


def prepare(data, request_all=False):
    if request_all:
        prepared_data = []
        for download_object in data:
            if 'History' in download_object.__class__.__name__:
                prepared_data.append(prep_history(download_object))
            else:
                prepared_data.append(prep_queue(download_object))
    else:
        if 'History' in data.__class__.__name__:
            prepared_data = prep_history(data)
        else:
            prepared_data = prep_queue(data)
    return prepared_data




def history(request):
    try:
        pk = request.GET['pk']
        #single item from history removed, update database
        Download_History.objects.get(pk=pk).delete()
        return HttpResponse("")
    except:
        #request for history database
        hist = prepare(Download_History.objects.all().order_by("-time"), True)
        return JsonResponse(hist, safe=False)


def clear_history(request):
    Download_History.objects.all().delete()
    return HttpResponse("")


def cancel_download(request):
    down = Download_Ongoing.objects.latest("id")
    try:
        #in this case, the download is canceled by the javascript, the item has to be put back at the end of the queue
        queuing = request.GET['queuing']
        down.status, down.speed, down.progress, down.completed, down.eta, down.timeleft, down.active = "Replaced into queue", None, None, None, None, None, False
        down.save()
        backup = Resume_Backup.objects.latest("id")
        queue = Download_Queue(title=backup.title, sizeraw=backup.sizeraw, network=backup.network, channel=backup.channel, username=backup.username, number=backup.number)
        queue.save()
        queue = prepare(queue)
        return JsonResponse(queue, safe=False)
    except:
        if request.GET['par'] == "cancel":        
            down.status, down.speed, down.progress, down.completed, down.eta, down.timeleft, down.active = "Canceled", None, None, None, None, None, False
        else:
            if not down.status=="Canceled":
                down.status, down.speed, down.progress, down.completed, down.eta, down.timeleft, down.active = "Shutdown", None, None, None, None, None, True
        down.save()
        return HttpResponse("canceled")



def monitor(request):
    #work around with time.sleep for a weird problem : first database call fails, maybe needs time to load ?
    for x in range(20):
        if Download_Ongoing.objects.all().count() > 0:
            try:
                monitor = serializers.serialize('json', Download_Ongoing.objects.filter(pk=Download_Ongoing.objects.latest("id").id))
                download_object = Download_Ongoing.objects.latest("id")
                monitor = json.loads(monitor)[0]
                #prepare data
                del monitor['model']
                monitor['fields']['attempts'] = Resume_Backup.objects.latest("id").attempts
                if download_object.eta:
                    if localtime(download_object.eta).date() == utcnow().date():
                        monitor['fields']['eta'] = localtime(download_object.eta).time().strftime('%H:%M:%S')
                    else:
                        monitor['fields']['eta'] = localtime(download_object.eta).strftime('%d %b %H:%M:%S')
                if download_object.timeleft:
                    if download_object.timeleft > 3600:
                        monitor['fields']['timeleft'] = time.strftime('%H h %M min %S sec', time.gmtime(download_object.timeleft))
                    elif download_object.timeleft > 60:
                        monitor['fields']['timeleft'] = time.strftime('%M min %S sec', time.gmtime(download_object.timeleft))
                    else:
                        monitor['fields']['timeleft'] = time.strftime('%S sec', time.gmtime(download_object.timeleft))
                if download_object.completed:
                    if download_object.completed/(1024**2) >= 1000:
                        monitor['fields']['completed'] = format_number(download_object.completed, "GB")
                    else:
                        monitor['fields']['completed'] = format_number(download_object.completed)
                if download_object.sizeraw:
                    if download_object.sizeraw/(1024**2) >= 1000:
                        monitor['fields']['size'] = format_number(download_object.sizeraw, "GB")
                    else:
                        monitor['fields']['size'] = format_number(download_object.sizeraw)

                return JsonResponse(monitor, safe=False)

            except Exception as e:
                print (e)
                return HttpResponse("ongoing down")
        time.sleep(0.1)
    return HttpResponse("")


def shutdown_server(request):
    par = request.GET['par']
    if par == "render":
        return render(request, 'shutdown.html')
    else:
        ''' This method works fine to shutdown, but not to restart, in case the actual system is buggy
        import signal
        with open(os.path.join(settings.BASE_DIR, 'IRCapp.pid'), "r") as mypid:    
            content = mypid.readlines()
            PID = int(content[0].strip())
        os.kill(PID, signal.SIGTERM)  
        '''     
        cherrypy.engine.exit()
        return HttpResponse("completed")

def restart_server(request):
    par = request.GET['par']
    if par == "render":
        return render(request, 'restart.html')
    else:
        cherrypy.engine.restart()
        return HttpResponse("restarted")    
    
def shutdown(request):
    if platform.system() == 'Windows':
        os.system("shutdown /s")
        """ Shutdown Windows system, never returns, SABNZBD system

        try:
            import win32security
            import win32api
            import ntsecuritycon

            flags = ntsecuritycon.TOKEN_ADJUST_PRIVILEGES | ntsecuritycon.TOKEN_QUERY
            htoken = win32security.OpenProcessToken(win32api.GetCurrentProcess(), flags)
            id_ = win32security.LookupPrivilegeValue(None, ntsecuritycon.SE_SHUTDOWN_NAME)
            newPrivileges = [(id_, ntsecuritycon.SE_PRIVILEGE_ENABLED)]
            win32security.AdjustTokenPrivileges(htoken, 0, newPrivileges)
            win32api.InitiateSystemShutdown("", "", 30, 1, 0)
        finally:
            os._exit(0)
        """
    elif platform.system() == 'Darwin':
        """ Shutdown OSX system, never returns
        """
        try:
            subprocess.call(['osascript', '-e', 'tell app "System Events" to shut down'])
        except:
            log.write('Error while shutting down system')
        os._exit(0)
    else:
        try:
            import dbus
            sys_bus = dbus.SystemBus()
            ck_srv = sys_bus.get_object('org.freedesktop.ConsoleKit',
                                            '/org/freedesktop/ConsoleKit/Manager')
            ck_iface = dbus.Interface(ck_srv, 'org.freedesktop.ConsoleKit.Manager')
            stop_method = ck_iface.get_dbus_method("Stop")
            stop_method()
        except:
            log.write('DBus does not support Stop (shutdown)')
        os._exit(0)

def queue(request):
    try:
        pk = request.GET['pk']
        #item from queue removed, update database
        Download_Queue.objects.get(pk=pk).delete()
        return HttpResponse("")
    except:
        #request for queue database
        queue = prepare(Download_Queue.objects.all().order_by("-id"), True)
        return JsonResponse(queue, safe=False)

def download_settings(request):
    down = Download_Settings.objects.latest('id')
    if request.method == 'POST':
        body = request.body.decode('utf-8')
        if "downbox" in body:
            down.download_box = int(body.split("=")[1])
            down.save()
            return HttpResponse("")
        else:
            down.shutdown = int(body.split("=")[1])
            down.save()
            return HttpResponse("")
    else:
        if request.GET['data'] == 'downbox':
            downbox = down.download_box
            return JsonResponse({'state' : downbox}, safe=False)
        else:
            shutdown = down.shutdown
            return JsonResponse({'state' : shutdown}, safe=False)

def search(request):
    q = request.GET['q']
    try:
        pn = int(request.GET['pn'])
    except:
        pn = 0
    try:
        noquick = request.GET['noquick']
    except:
        noquick = False
    result = getinfo(q, pn)
    contain=[]
    if Quick_Download_Contains.objects.all():
        for x in Quick_Download_Contains.objects.all():
            contains={}
            contains['id'] = x.id
            contains['text'] = x.contains
            contain.append(contains)
    exclude=[]
    if Quick_Download_Excludes.objects.all():
        for x in Quick_Download_Excludes.objects.all():
            excludes = {}
            excludes['id'] = x.id
            excludes['text'] = x.excludes
            exclude.append(excludes)    
    downbox = Download_Settings.objects.latest('id').download_box
    pathinstance = Download_Path.objects.latest('id')
    pathform = PathForm(instance=pathinstance)
    context = {
        'directory' : directory(),
        'free_space' : get_free_space_mb(),
        'pathform' : pathform,
        'q' : q,
        'noquick' : noquick,
        'contains' : contain,
        'excludes' : exclude,        
        'downbox' : downbox
    }
    try:
        context['results'] = result["results"]
        context['num'] = result["num"]
        context['pn'] = result["pn"]
    except:
        context['message'] = result

    return render(request, 'results.html', context)

    

def quickinfo(querystring):
    #for quickdownload
    i = 0
    total = []
    while True:
        try:
            par = { 'q' : querystring, 'pn' : i, 'cid' : '275' }
            data = requests.get("http://ixirc.com/api/", params=par)
        except:
            log("Couldn't access ixirc search engine, exiting.").write()
            return "Couldn't access ixirc search engine, is there a problem with your internet connexion?"

        i += 1
        data = json.loads(data.text)

        try:
            if len(data["results"]) == 0:
                #quick download impossible
                return ""
        except:
            #quick download impossible
            return ""


        filtered = []
        query = querystring.split(" ")
        for x in data["results"][:]:
            test = True
            for element in query:
                if not element in x["name"].lower():
                    test = False
            if Quick_Download_Contains.objects.all().count() > 0:
                for obj in Quick_Download_Contains.objects.all():
                    if not str(obj.contains).lower() in x["name"].lower():
                        test = False
            if Quick_Download_Excludes.objects.all().count() > 0:
                for obj in Quick_Download_Excludes.objects.all():
                    if str(obj.excludes).lower() in x["name"].lower():
                        test = False
            if test:
                filtered.append(x)
        if not (len(data["results"]) % 30 == 1 and len(data["results"]) != 1): break


    for result in filtered:
        if testresult(result):
            #testresult removes all incomplete results
            total.append(result)

    if len(total) == 0:
        return ""
    #from this point on, every element in total matches the key words. Next step is the quality check
    quality_list = ['MAXI', 'EXCE', 'GOOD', 'NORM']
    quality_words = ['bluray', '1080', '720', 'hd']
    quality_index =  quality_list.index(Quick_Download.objects.latest('id').priority)
    #first loop through all the keywords
    for word in quality_words[quality_index:]:
        #for each key word, loop through all the elements to find a match before doing the same for the next keyword
        for x in total:
            if word in x["name"].lower():
                #also, if word is "hd", exclude other words since x["name"] might be like "720p.HDTV"
                test = True
                for otherword in quality_words[:quality_index]:
                    if otherword in x["name"].lower():
                        test = False
                if test:
                    total = x
                    return total
    if type(total) == list:
        total = total[0]

    return total

def getinfo(querystring, pn=0):
    #for normal search
    try:
        #normal search
        par = {"q" : querystring, "pn" : pn}
        data = requests.get("http://ixirc.com/api/", params=par)
    except:
        log("Couldn't access ixirc search engine, exiting").write()
        return "Couldn't access ixirc search engine, is there a problem with your internet connexion?"

    data = json.loads(data.text)

    if data["c"] == 0:
        log("No match for %s on the search engine" % querystring).write()
        return "No match for “%s” on the search engine" % querystring

    try:
        num = len(data["results"])
        for result in data["results"][:]:
            #print (result["cname"], result["cid"])
            if testresult(result) is False:
                data["results"].remove(result)
                #quick download impossible
    except:
        #quick download impossible
        return "No match for “%s” on the search engine" % querystring

    if len(data["results"]) == 0:
        return "No match for “%s” on the search engine" % querystring

    results = data["results"]

    response = {"results" : results, "num" :  num, "pn" : pn}

    return response

def testresult(result):

    try:
        server = result["naddr"]
        channel = result["cname"]
        xdccbot = result["uname"]
        xdccrequest = result["n"]
        size = result["sz"]
    except:
        return False
    else:
        if size == 0:
            return False
        else:
            return True
