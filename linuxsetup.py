from setuptools import setup
import os

data_files = [
    ('share/applications/', ['IRCapp.desktop']),
    ('share/icons/hicolor/scalable/apps/', ['ircapp/core/static/ircapp_bolt.svg']),
    ('lib/python3/dist-packages/', ['rarfile.py']),
    ('lib/python3/dist-packages/', ['inflect.py'])
]

def copy_rec(root_dir):
    mylist = []
    for (dirpath, dirnames, filenames) in os.walk(root_dir):
        for f in filenames:
            mylist.append(("lib/python3/dist-packages/" + dirpath + "/", [os.path.join(dirpath, f)]))
    return mylist

data_files += copy_rec("ircapp")

version = exec(open('ircapp/version.py').read())
setup(name='ircapp',
      # Keep version in sync with stdeb/__init__.py and install section
      # of README.rst.
      version=version,
      author='MrJ',
      description='Simple IRC Client',
      license='MIT',
      url='https://github.com/themadmrj/ircapp',
      #packages = ['ircapp'],
      #packages = ['ircapp/', 'django', 'irc', 'requests', 'cherrypy', 'pytz'],
      entry_points = {
        'gui_scripts' : ['ircapp = ircapp.main:start_ircapp']
      },
      data_files = data_files,

)

