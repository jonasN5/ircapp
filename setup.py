from setuptools import setup
import os

data_files = [
    ('share/applications/', ['ircapp.desktop']),
    ('share/icons/hicolor/scalable/apps/', ['ircapp/core/static/ircapp_bolt.svg'])
]

def copy_rec(root_dir):
    mylist = []
    for (dirpath, dirnames, filenames) in os.walk(root_dir):
        for f in filenames:
            mylist.append(("lib/python3/dist-packages/" + dirpath + "/", [os.path.join(dirpath, f)]))
    return mylist

data_files += copy_rec("ircapp")

# Note: rarfile, names and dataclasses_json are required but not available as debian packages so we include them in the app directly
setup(name='ircapp',
      version='3.0.0',
      author='MrJ',
      description='Simple IRC Client',
      license='MIT',
      url='https://github.com/themadmrj/ircapp',
      entry_points={
          'gui_scripts': ['ircapp = ircapp.main:start_app']
      },
      data_files=data_files,
      install_requires=[
          'django>=3.2.7',
          'irc>=19.0.1',
          'requests>=2.22.0',
          'miniupnpc>=2.0.2',
          'cherrypy>=18.6.1',
          'pytz>=2019.3',		
          'easygui>=0.98.2'
      ]
      )

