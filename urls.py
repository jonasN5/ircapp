from django.conf.urls import patterns, url
import views
from django.views.generic.base import RedirectView


urlpatterns = patterns('',
    url(r'^favicon.ico$', RedirectView.as_view(url='/core/static/favicon.ico', permanent=False),name="favicon"),  
    url(r'^$', views.index, name='index'), #search.html
    url(r'^quick_download/$', views.quick_download, name='quick_download'), #quick download button
    url(r'^send_file/$', views.send_file, name='send_file'), #send a file button
    url(r'^dcctransfer_information/$', views.dcctransfer_information, name='dcctransfer_information'), #get nickname & password
    url(r'^preferences/$', views.preferences, name='preferences'), #quick download preferences in preferences.html
    #url(r'^report_bug/$', views.report_bug, name='report_bug'), #bug report ; use mailto: and attach log.txt to provide details for further testing
    url(r'^download_settings/$', views.download_settings, name='download_settings'), #download box & shutdown option
    url(r'^log/$', views.read_log, name='log'), #show logfile to user
    url(r'^restart_server/$', views.restart_server, name='restart_server'), #restart IRCapp (shutdown + reload)
    url(r'^shutdown_server/$', views.shutdown_server, name='shutdown_server'), #shutdown IRCapp, the Cherrypy server and free up the port
    url(r'^shutdown/$', views.shutdown, name='shutdown'), #shutdown computer on download/queue finish  
    url(r'^opendir/$', views.opendir, name='opendir'), #ajax on click event to open file directory
    url(r'^delete_pref/$', views.delete_pref, name='delete_pref'), #delete a term in "contains" or "excludes"
    url(r'^search/$', views.search, name='search'), #results.html
    url(r'^monitor/$', views.monitor, name='monitor'), #Download_Ongoing monitoring, ajax calls with 1 sec delay
    url(r'^upload_monitor/$', views.upload_monitor, name='upload_monitor'), #Upload_Ongoing monitoring, ajax calls with 1 sec delay
    url(r'^search_download/$', views.search_download, name='search_download'), #ajax download launched on item click in results.html
    url(r'^history/$', views.history, name='history'), #ajax call to get history for search.html
    url(r'^clear_history/$', views.clear_history, name='clear_history'), #ajax call (via clear button) to clear the whole history database
    url(r'^cancel_download/$', views.cancel_download, name='cancel_download'), #ajax call to cancel ongoing download : cancel.txt created and deamon thread stops
    url(r'^cancel_upload/$', views.cancel_upload, name='cancel_upload'), #ajax call to cancel ongoing upload 
    url(r'^download_path/$', views.download_path, name='download_path'), #form submission (POST) to change the download directory    
    url(r'^space/$', views.space, name='space'), #ajax call to update harddrive space continuously       
    url(r'^queue/$', views.queue, name='queue'), #ajax call to get queue for search.html as well as posting new item to queue, both on quickdownload button and item click in results.html
      
)
