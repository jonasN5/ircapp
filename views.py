from core.logs import directory, log
from core.upload import upload_file
from core.models import *
from core.forms import *
import main
import core.download

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.core import serializers
import requests
import sys, json
import ctypes
import os, subprocess
import platform
import time
import settings
import datetime
from django.utils.timezone import localtime
from django.utils.timezone import now as utcnow
import cherrypy
import tkinter as tk
from tkinter.ttk import *
from tkinter import filedialog
import random, string


       
"""
main view when loading IRC app
"""

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
        'quickdown_value' : quickdown_value,
        'contains' : contain,
        'excludes' : exclude,
        'pathform' : pathform,
        'downbox' : downbox,
    }
    return render(request, 'search.html', context)
    
"""
this part is to download ; there are 2 methods :
-quick download (using the bolt)
-download through the search engine with clicking a result
"""

def quick_download(request):
    q = request.GET['q']
    data = quickinfo(q)
    print (data)
    if data:
        #quick download enabled : download without displaying results
        search_download(request, data=data)
        return HttpResponse("")
    else:
        #no match found with quick download method
        #display search results instead
        return JsonResponse({ 'redirect' : True, 'q' : q }, safe=False)


def search_download(request, data={}):
    """
    internal purpose only, not a view
    """
    if data:
        sizeraw, server, channel, xdccbot, xdccrequest = (int(data["sz"]), data["naddr"],
            data["cname"],  data["uname"], data["n"])
        filename = data["name"]
    else:   
        filename = request.GET['filename']
        data = request.GET['data']
        sizeraw, server, channel, xdccbot, xdccrequest = data.split(",")[0:]
    if get_free_space_mb() <= int(sizeraw)/(1024**3):
        #not enough disk space, add to queue without further checking
        queue = Download_Queue(filename=filename, sizeraw=int(sizeraw), server=server, channel=channel, username=xdccbot, package_number=xdccrequest)
        queue.save()
        queue = prepare(Download_Queue.objects.latest("id"))
        queue["type"] = "queue"
        return JsonResponse(queue, safe=False)        
    if Download_Ongoing.objects.all().count() > 0:
        #a least one download is in progress, check server & channel
        for download_ongoing in Download_Ongoing.objects.all():
            if download_ongoing.server == server:
                #if same package, don't do anything
                if (download_ongoing.channel == channel and download_ongoing.username == xdccbot and
                    download_ongoing.package_number == xdccrequest):
                    return HttpResponse("Package already requested")
                (download_ongoing.channel == channel and download_ongoing.username == xdccbot)
                if (download_ongoing.channel == channel and download_ongoing.username == xdccbot) or \
                        (Download_Settings.objects.latest('id').queue_similar and download_ongoing.filename.split(".")[0] == filename.split(".")[0]):
                    #same server, channel and bot OR queue_similar checked + name check: add to queue
                    queue = Download_Queue(filename=filename, sizeraw=int(sizeraw), server=server, channel=channel, username=xdccbot, package_number=xdccrequest)
                    queue.save()
                    queue = prepare(Download_Queue.objects.latest("id"))
                    queue["type"] = "queue"
                    return JsonResponse(queue, safe=False)                      
                else:
                    #same server exists but different channel : signal bot to join new channel and request package
                    #provide filename and size for GUI purpose
                    botqueue = main.queuedict[server+download_ongoing.username]
                    botqueue.put(channel+","+xdccbot+","+str(xdccrequest)+","+filename+","+str(sizeraw))
                    return HttpResponse("")
    #no download in progress or download in progress on another server : launch new bot with download
    core.download.xdcc(filename=filename, size=sizeraw, server=server, 
        channel=channel, username=xdccbot, package_number=xdccrequest)    
    #hist = prepare(Download_History.objects.latest("id"))
    #hist["type"] = "history"
    hist = ""
    return JsonResponse(hist, safe=False)
    
def manage_queue(down_ongoing):
    """
    internal purpose only, not a view
    """  
    """
    the queue has to be checked and managed in 2 cases :
    -when a download finishes
    -when a download is canceled
    """

    botqueue = main.queuedict[down_ongoing.server+down_ongoing.username]
    #first check if there is a queue for this server
    if Download_Queue.objects.all().count() > 0:
        if Download_Queue.objects.filter(server=down_ongoing.server):
            #queue exists for this server, channel & bot, request next package
            queue_obj = Download_Queue.objects.filter(server=down_ongoing.server).order_by("id")[0]
            if queue_obj.username == down_ongoing.username:
                botqueue.put("queue_item,"+queue_obj.filename+","+str(queue_obj.sizeraw)+","+str(queue_obj.package_number))
            else:
                del main.queuedict[down_ongoing.server+down_ongoing.username]
                down_ongoing.delete()
                botqueue.put(queue_obj.channel+","+queue_obj.username+","+str(queue_obj.package_number)+","+queue_obj.filename+","+str(queue_obj.sizeraw))                
            #download_ongoing item is maintained and data is replaced by new package info
            #queue item has to be deleted
            queue_obj.delete()  
            return          
    #no queue -at all or for this server-;
    #if no more DCCconnection is live for this server, quit the server
    if not Download_Ongoing.objects.exclude(pk=down_ongoing.id).filter(server=down_ongoing.server, active=True):
        print("stop signal")
        botqueue.put("stop")
    #the following commented section sometimes leads to an infinite loop, needs a detailed fix
    """
    make sure the stop signal has been passed to the bot before deleting the queue
    while not botqueue.empty():
        time.sleep(0.2)   
    """    
    print ("removing %s from queue" % down_ongoing.server)
    del main.queuedict[down_ongoing.server+down_ongoing.username]
    down_ongoing.delete()
    #also check if shutdown option is checked
    if Download_Settings.objects.latest('id').shutdown:
        shutdown()

def initial_download(obj, what="resume"):
    """
    internal purpose only, not a view
    """
    if what != "resume":
        core.download.xdcc(filename=obj.filename, size=obj.sizeraw, server=obj.server, 
            channel=obj.channel, username=obj.username, package_number=obj.package_number)
    else:          
        core.download.xdcc(filename=obj.filename, size=obj.sizeraw, server=obj.server, 
            channel=obj.channel, username=obj.username, package_number=obj.package_number, down_obj=obj, resume=True)    
    
    
"""
this part is to monitor the download/upload, 
e.g. return its state and various information
"""
def format_monitor(download_object):
    """
    internal purpose only, not a view
    """
    monitor = serializers.serialize('json', [download_object,])
    monitor = json.loads(monitor)[0]
    #prepare data
    del monitor['model']
    #monitor['fields']['attempts'] = Resume_Backup.objects.latest("id").attempts
    monitor['fields']['id'] = download_object.id
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
    return monitor
    
                                    
def monitor(request):
    if Download_Ongoing.objects.all().count() > 0:
        monitorlist = []
        monitorlist.append(Download_Ongoing.objects.all().count())
        if Download_Ongoing.objects.all().count() > 1:
            for download_object in Download_Ongoing.objects.all():                
                monitor = format_monitor(download_object)
                monitorlist.insert(1, monitor)
        else:
            monitor = format_monitor(Download_Ongoing.objects.latest("id"))
            monitorlist.append(monitor)
        #we append this in case the GUI needs an update (queue/history)
        if int(request.GET['history_count']) != Download_History.objects.all().count() or (
            int(request.GET['queue_count']) != Download_Queue.objects.all().count()):
            monitorlist.append("update_elements")
        return JsonResponse(monitorlist, safe=False)

    return HttpResponse("")
    

def upload_monitor(request):
    #workaround with time.sleep for a weird problem : first database call fails, maybe needs time to load ?
    for x in range(20):
        if Upload_Ongoing.objects.all().count() > 0:
            try:
                monitor = serializers.serialize('json', Upload_Ongoing.objects.filter(pk=Upload_Ongoing.objects.latest("id").id))
                upload_object = Upload_Ongoing.objects.latest("id")
                monitor = json.loads(monitor)[0]
                #prepare data
                del monitor['model']
                if upload_object.eta:
                    if localtime(upload_object.eta).date() == utcnow().date():
                        monitor['fields']['eta'] = localtime(upload_object.eta).time().strftime('%H:%M:%S')
                    else:
                        monitor['fields']['eta'] = localtime(upload_object.eta).strftime('%d %b %H:%M:%S')
                if upload_object.timeleft:
                    if upload_object.timeleft > 3600:
                        monitor['fields']['timeleft'] = time.strftime('%H h %M min %S sec', time.gmtime(upload_object.timeleft))
                    elif upload_object.timeleft > 60:
                        monitor['fields']['timeleft'] = time.strftime('%M min %S sec', time.gmtime(upload_object.timeleft))
                    else:
                        monitor['fields']['timeleft'] = time.strftime('%S sec', time.gmtime(upload_object.timeleft))
                if upload_object.completed:
                    if upload_object.completed/(1024**2) >= 1000:
                        monitor['fields']['completed'] = format_number(upload_object.completed, "GB")
                    else:
                        monitor['fields']['completed'] = format_number(upload_object.completed)
                if upload_object.sizeraw:
                    if upload_object.sizeraw/(1024**2) >= 1000:
                        monitor['fields']['size'] = format_number(upload_object.sizeraw, "GB")
                    else:
                        monitor['fields']['size'] = format_number(upload_object.sizeraw)

                return JsonResponse(monitor, safe=False)

            except Exception as e:
                print (e)
                return HttpResponse("ongoing upload")
        time.sleep(0.1)
    return HttpResponse("")    
    

"""
this part is for the search engine and quick downloading utilities
The "settingsbox" is included, since its purpose is to configure the quick download function
"""
    
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
    """
    internal purpose only, not a view
    """
    #for quickdownload
    i = 0
    total = []
    while True:
        try:
            par = { 'q' : querystring, 'pn' : i }
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

        query = querystring.split(" ")
        quality_list = ['MAXI', 'EXCE', 'GOOD', 'NORM']
        quality_words = ['bluray', '1080', '720', 'hd']
        quality_index =  quality_list.index(Quick_Download.objects.latest('id').priority)        
        for x in data["results"][:]:
            test = True
            for element in query:
                if not element in x["name"].lower():
                    test = False
                    print (element, x["name"].lower())
            if Quick_Download_Contains.objects.all().count() > 0:
                for obj in Quick_Download_Contains.objects.all():
                    if not str(obj.contains).lower() in x["name"].lower():
                        test = False
            if Quick_Download_Excludes.objects.all().count() > 0:
                for obj in Quick_Download_Excludes.objects.all():
                    if str(obj.excludes).lower() in x["name"].lower():
                        test = False
                       
            #first loop through all the keywords
            for word in quality_words[quality_index:]:
                #for each key word, loop through all the elements to find a match before doing the same for the next keyword
                if word in x["name"].lower():
                    if word == "hd":
                        #also, if word is "hd", exclude other words since x["name"] might be like "720p.HDTV"
                        for otherword in quality_words[:quality_index]:
                            if otherword in x["name"].lower():
                                test = False

                else:
                    test = False
            if test and testresult(x):
                return x               
        if not (len(data["results"]) % 30 == 1 and len(data["results"]) != 1): break


def getinfo(querystring, pn=0):
    """
    internal purpose only, not a view
    """
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
    """
    internal purpose only, not a view
    """
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
                    

"""
these are some functions used to :
-return disk free space
-return download directory
-open download directory on click
-display log in browser
""" 
    
def get_free_space_mb():
    """
    Return folder/drive free space (in megabytes).
    internal purpose only, not a view
    """    
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
    if Download_Ongoing.objects.all().count() > 0:
        if Download_Ongoing.objects.latest('id').active == True and Download_Ongoing.objects.latest('id').status != "Interrupted":
            msg = u_('Cannot change the download directory while downloading. Please wait for your download to finish.')
            return JsonResponse({ 'error' : msg, }, safe=False)
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    path = filedialog.askdirectory()
    if not path:
        return HttpResponse("")
    if Download_Path.objects.all().count() > 0:
        obj = Download_Path.objects.latest('id')
        obj.download_path = path
        obj.save()
    else:
        new_path = Download_Path(download_path=path).save()
    root.destroy()
    return JsonResponse({ 'success' : path, }, safe=False)

def splitext(path):
    """
    internal purpose only, not a view
    """
    for ext in ['.tar.gz', '.tar.bz2']:
        if path.endswith(ext):
            return path[:-len(ext)], path[-len(ext):]
    return os.path.splitext(path)

def opendir(request):
    pk, myclass = int(request.GET['pk']), request.GET['myclass']
    if directory():
        basefolder = directory()
        foldername = basefolder
        if myclass == "history":
            fileobject = Download_History.objects.get(pk=pk)
            if "extracted" in fileobject.status and ".tar" in splitext(fileobject.filename)[1]:
                foldername = os.path.join(basefolder, splitext(fileobject.filename)[0])           
        else:
            fileobject = Download_Ongoing.objects.get(pk=pk)
            if "Extracting" in fileobject.status and ".tar" in splitext(fileobject.filename)[1]:
                foldername = os.path.join(basefolder, '_UNPACK_' + splitext(fileobject.filename)[0])
            elif "extracted" in fileobject.status and ".tar" in splitext(fileobject.filename)[1]:
                foldername = os.path.join(basefolder, splitext(fileobject.filename)[0])
        if sys.platform == "win32":
            os.startfile(foldername)
        else:
            opener ="open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, foldername])
        return HttpResponse("succefully opened directory")
    else:
        return HttpResponse("No directory set to open dir") 

        
def read_log(request):
    log_file = open(log().my_log)
    response = HttpResponse(content=log_file)
    response['Content-Type'] = 'text/plain'
    log_file.close()
    return response        

"""
this is the part used for direct file transfer to another IRCapp user ;
upload and download
""" 

def dcctransfer_information(request):
    nick = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
    pw = ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(12))
    core.download.xdcc(nick=nick, pw=pw)
    return JsonResponse({ 'nick' : nick, 'password' : pw }, safe=False)

#send file feature
def send_file(request):
    nickname = request.GET['nick']
    password = request.GET['pw']
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    path = filedialog.askopenfilename() 
    if not path:
        return HttpResponse("")
    root.destroy()
    if Upload_Ongoing.objects.all().count() > 0:
        #direct filet transfer already ongoing
        return HttpResponse("")
    else:
        upload_file(path, nickname, password)
        return JsonResponse({ 'msg' : "success" }, safe=False)



"""
here are two views to return the full queue and history; plus one to clear the whole history
they come with some formating functions to help preparing for the GUI output
""" 

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

def prep_history(download_object):
    """
    internal purpose only, not a view
    """
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
    """
    internal purpose only, not a view
    """
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
    """
    internal purpose only, not a view
    """
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


def format_number(number, num_format="MB"):
    """
    internal purpose only, not a view
    """
    if num_format == "kB":
        return str(int(number/1024)) + " " + num_format
    elif num_format == "MB":
        return str(int(number/(1024**2))) + " " + num_format
    else:
        return str(round(number/(1024**3), 2)) + " " + num_format


"""
Miscellaneous :
-cancel an ongoing download
-get the settings (for instance if download box is displayed), mainly to redisplay properly when user hits F5
""" 

def cancel_download(request):
    print ("cancel pressed")
    down = Download_Ongoing.objects.get(pk=request.GET['id'])
    print ("down that should be canceled is : %s %s" % (down.server, down.username))
    down.active = False
    down.save()
    botqueue = main.queuedict[down.server+down.username]
    botqueue.put("cancel") 
    return HttpResponse("canceled")

def cancel_upload(request):
    up = Upload_Ongoing.objects.latest("id")
    botqueue = main.queuedict[up.server+up.username]
    botqueue.put("cancel") 
    return HttpResponse("upload canceled")    

def download_settings(request):
    down = Download_Settings.objects.latest('id')
    if request.method == 'POST':
        body = request.body.decode('utf-8')
        if "downbox" in body:
            down.download_box = int(body.split("=")[1])
        elif "queue_similar" in body:
            down.queue_similar = int(body.split("=")[1])
        else:
            down.shutdown = int(body.split("=")[1])
        down.save()
        return HttpResponse("")
    else:
        data = {
            'downbox' : down.download_box,
            'queue_similar' : down.queue_similar,
            'shutdown' : down.shutdown
        }
        return JsonResponse(data, safe=False)

"""
application wide functions :
-shutdown and restart IRCapp
-shutdown computer on download finish
""" 

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
        if main.queuedict:
            for server, botqueue in main.queuedict.items():
                botqueue.put("stop")
        cherrypy.engine.exit()
        return HttpResponse("completed")

def restart_server(request):
    par = request.GET['par']
    if par == "render":
        obj = Download_Settings.objects.latest('id')
        obj.restart = True
        obj.save()
        return render(request, 'restart.html')
    elif par == "respawn":
        return HttpResponse("restarted")
    else:
        if main.queuedict:
            for server, botqueue in main.queuedict.items():
                botqueue.put("stop")
            main.queuedict = {}
        cherrypy.engine.restart()
        return HttpResponse("completed")               
   
    
def shutdown():
    """
    internal purpose only, not a view
    """
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
