import sys         
from cx_Freeze import setup,Executable
import os, pytz, shutil


base = None
appname="IRCapp"
include_msvcr = False
rarfile = 'rarfile'
if sys.platform == "win32":
    include_msvcr = True
    appname="IRCapp.exe"
    base = "Win32GUI"
    rarfile = 'unrar'
    
    
includefiles = ['templates/', 'urls.py', 'views.py', 'ircapp/', 'settings.py', '__init__.py', 'config.ini']
packages = ['http.cookies', 'html.parser', 'django', 'irc', 'requests', rarfile, 'cherrypy']
includes = ['PIL._imaging.so']

srcDir = os.path.dirname( pytz.__file__ )
dstDir = os.path.join( 'build', 'pytz' )
shutil.copytree( srcDir, dstDir)

setup(
    name = 'IRCapp',
    version = '1.1',
    description = 'Simple IRC app based on irclib to download quickly using the ixirc search engine',
    author = 'MrJ',
    author_email = 'ircappwebmaster@gmail.com',
    options = {'build_exe': {'include_files':includefiles, 'packages':packages, "excludes": ['pytz', 'ircapp'], "include_msvcr" : include_msvcr}}, 
    executables = [Executable('main.py', icon='ircapp/static/favicon.ico', base=base, targetName=appname)]
)
