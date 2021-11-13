# setup for cx_freeze to freeze the application

import sys, os
# from cx_Freeze import setup, Executable
from setuptools import setup, find_packages
from ircapp.ircapp.version import __version__

data_files = [
    (os.path.join('share', 'applications'), ['ircapp.desktop']),
    (os.path.join('share', 'icons', 'hicolor', 'scalable', 'apps'),
     ['ircapp/core/static/ircapp_bolt.svg'])
]

base = None
appname = "IRCapp"
include_msvcr = False
rarfile = 'rarfile'
if sys.platform == "win32":
    shutil.copyfile(os.path.join(os.path.dirname(sys.executable), 'unrar.dll'), os.path.join('build', 'UnRAR.dll'))
    include_msvcr = True
    appname = "IRCapp.exe"
    base = "Win32GUI"
    rarfile = 'unrar'

includefiles = ['ircapp/']
packages = ['django', 'irc', 'requests', rarfile, 'cherrypy', 'miniupnpc', 'easygui', 'names', 'dataclasses_json']

setup(
    name='IRCapp',
    version=__version__,
    description='Simple IRC app based on irclib',
    author='MrJ',
    data_files=data_files,
    license='MIT',
    url='https://github.com/themadmrj/ircapp',
    packages=find_packages(exclude=['*test*']),
    options={'build_exe': {'include_files': includefiles, 'packages': packages, 'include_msvcr': include_msvcr}},
    entry_points={
        'gui_scripts': ['ircapp = ircapp.main:start_app']
    },
    include_package_data=True,
    install_requires=packages
)