#this is a backup file; cx freeze didnt work under windows, had to use py2exe; problem is fixed now
import sys, os     
from distutils.core import setup
import py2exe
import pytz, shutil

maindir = os.path.dirname(os.path.abspath(__file__))
def copy_dir(dir):
    dir_path = dir
    base_dir = os.path.join(maindir, dir_path)
    for (root, dirs, files) in os.walk(base_dir):
        for f in files:
            yield os.path.join(root, f)

Mydata_files = [
    ('templates', [f for f in copy_dir('templates')]),
    ('ircapp', [f for f in copy_dir('ircapp') if not 'static' in f and not 'cache' in f]),
    ('ircapp/static', [f for f in copy_dir('ircapp/static')]),
]

Mydata_files += [
            ('', [os.path.join(maindir, 'urls.py')]),
            ('', [os.path.join(maindir, 'views.py')]),
            ('', [os.path.join(maindir, 'settings.py')]),
            ('', [os.path.join(maindir, 'db.sqlite3')]),
            ('', [os.path.join(maindir, '__init__.py')]),
            ('', [os.path.join(maindir, 'config.ini')]),
            ('', ['C:\\Windows\\System32\\msvcp100.dll']),
            ('', ['C:\\Windows\\System32\\msvcr100.dll']),
]


srcDir = os.path.dirname( pytz.__file__ )
dstDir = os.path.join( 'dist', 'pytz' )
shutil.copytree( srcDir, dstDir)
        
#includefiles = ['favicon.ico', 'templates/', 'urls.py', 'views.py', 'ircapp/', 'db.sqlite3']
packages = ['http', 'html', 'django', 'irc', 'requests', 'unrar', 'setuptools', 'cherrypy']
#skip error msvcr100.dll missing
includes = []

icon = os.path.join(maindir, 'ircapp', 'static', 'favicon.ico')


setup(
    name = 'IRCapp',
    version = '1.0',
    description = 'Simple IRC app based on irclib to download quickly using the ixirc search engine',
    author = 'MrJ',
    data_files = Mydata_files,
    author_email = 'ircappwebmaster@gmail.com',
    options = {'py2exe': {'packages':packages, "excludes": ['pytz']}}, 
    windows = [{'script' : 'main.py', 'dest_base': 'IRCapp', 'icon_resources': [(1, icon)]}]
    
)
