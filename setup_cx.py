# Setup for cx_freeze to freeze the application under Windows: simply call py -m setup_cx.py build

import sys, os, shutil
from cx_Freeze import setup, Executable
from ircapp.ircapp.version import __version__

base = None
appname = "IRCApp"
include_msvcr = False
rarfile = 'rarfile'
if sys.platform == "win32":
    include_msvcr = True
    appname = "IRCApp.exe"
    base = "Win32GUI"
    rarfile = 'unrar'

includefiles = ['ircapp/']
packages = ['django', 'irc', 'requests', rarfile, 'cherrypy', 'miniupnpc', 'easygui', 'names', 'dataclasses_json']

setup(
    name=appname,
    version=__version__,
    description=appname,
    author='MrJ',
    license='MIT',
    url='https://github.com/themadmrj/ircapp',
    options={'build_exe': {'include_files':includefiles, 'packages': packages, 'include_msvcr': include_msvcr}},
    executables = [Executable('ircapp/main.py', icon='ircapp/core/static/favicon.ico', base=base, targetName=appname)]
)
