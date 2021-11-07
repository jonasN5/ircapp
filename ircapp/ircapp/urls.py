from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView

from core import views

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('favicon.ico/', RedirectView.as_view(url='/core/static/favicon.ico', permanent=False), name="favicon"),
    path('', views.Index.as_view(), name='index'),  # search.html
    path('quick_download/', views.QuickDown.as_view(), name='quick_download'),  # Quick download button
    path('send_file/', views.send_file, name='send_file'),  # send a file button
    path('dcctransfer_information/', views.dcctransfer_information, name='dcctransfer_information'),
    # get nickname & password
    path('preferences/', views.QuickDownPreferences.as_view()),  # quick download preferences in preferences.html
    path('download_settings/', views.DownSettings.as_view()),  # download box & shutdown option
    path('log/', views.read_log, name='log'),  # show logfile to user
    path('restart_server/', views.restart_server, name='restart_server'),  # restart IRCapp (shutdown + reload)
    path('shutdown_server/', views.shutdown_server, name='shutdown_server'),
    # shutdown IRCapp, the Cherrypy server and free up the port

    path('open_download_dir/', views.DownloadDir.as_view()),  # ajax on click event to open file directory
    path('search/', views.Search.as_view(), name='search'),  # results.html
    path('monitor/', views.Monitor.as_view(), name='monitor'),
    # DownloadOngoing monitoring, ajax calls with 1 sec delay
    path('upload_monitor/', views.upload_monitor, name='upload_monitor'),
    # UploadOngoing monitoring, ajax calls with 1 sec delay
    path('download/', views.Download.as_view(), name='download'),
    # Ajax download launched on item click in results.html
    path('history/', views.History.as_view()),  # ajax call to get history for search.html
    path('cancel_download/', views.CancelDownload.as_view()),
    # ajax call to cancel ongoing download : cancel.txt created and deamon thread stops
    path('cancel_upload/', views.cancel_upload, name='cancel_upload'),  # ajax call to cancel ongoing upload
    path('download_path/', views.DownloadPath.as_view(), name='download_path'),
    # form submission (POST) to change the download directory
    path('space/', views.space),  # ajax call to update harddrive space continuously
    path('queue/', views.Queue.as_view()) # ajax call to get queue for search.html as well as posting new item to queue, both on quickdownload button and item click in results.html
]
