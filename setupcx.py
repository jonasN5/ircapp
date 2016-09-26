#setup for cx_freeze to freeze the application
import sys         
from cx_Freeze import setup,Executable
import os, pytz, shutil, jaraco, sys


srcDir = os.path.dirname( pytz.__file__ )
dstDir = os.path.join( 'build', 'pytz' )
shutil.copytree( srcDir, dstDir)

base = None
appname="IRCapp"
include_msvcr = False
rarfile = 'rarfile'
if sys.platform == "win32":
    shutil.copyfile(os.path.join(os.path.dirname(sys.executable), 'unrar.dll'), os.path.join( 'build', 'UnRAR.dll' ))
    include_msvcr = True
    appname="IRCapp.exe"
    base = "Win32GUI"
    rarfile = 'unrar'
    
    
includefiles = ['templates/', 'urls.py', 'views.py', 'core/', 'settings.py', 'config.ini']
packages = ['http.cookies', 'html.parser', 'django', 'irc', 'requests', rarfile, 'cherrypy', 'miniupnpc', 'jaraco']
includes = ['PIL._imaging.so']

setup(
    name = 'IRCapp',
    version = '2.0.2',
    description = 'Simple IRC app based on irclib',
    author = 'MrJ',
    options = {'build_exe': {'include_files':includefiles, 'packages':packages, "excludes": ['pytz', 'core'], "include_msvcr" : include_msvcr}}, 
    executables = [Executable('main.py', icon='core/static/favicon.ico', base=base, targetName=appname)]
)
