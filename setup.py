from setuptools import setup, find_namespace_packages
import os

data_files = [
    ('share/applications/', ['ircapp.desktop']),
    ('share/icons/hicolor/scalable/apps/', ['ircapp/core/static/ircapp_bolt.svg']), 
    ('lib/python3/dist-packages/ircapp/', ['ircapp/favicon.ico']),
    ('lib/python3/dist-packages/ircapp/', ['ircapp/config.ini'])   
]

def copy_rec(root_dir):
    mylist = []
    for (dirpath, dirnames, filenames) in os.walk(root_dir):
        for f in filenames:
            mylist.append(("lib/python3/dist-packages/" + dirpath + "/", [os.path.join(dirpath, f)]))
    return mylist

data_files += copy_rec("ircapp/templates")
data_files += copy_rec("ircapp/core/static")


setup(name='ircapp',
      version='3.0.0',
      author='MrJ',
      description='Simple IRC Client',
      license='MIT',
      url='https://github.com/themadmrj/ircapp',
      packages=find_namespace_packages(include=['ircapp*'], exclude=['*tests*']),
      entry_points={
          'gui_scripts': ['ircapp = ircapp.main:start_app']
      },
      data_files=data_files,
      install_requires=[
          'django>=3.2.7',
          'irc>=19.0.1',
          'dataclasses_json>=0.5.6',
          'requests>=2.22.0',
          'miniupnpc>=2.0.2',
          'cherrypy>=18.6.1',
          'pytz>=2019.3',
          'names>=0.3.0',		
          'easygui>=0.98.2'
      ]
      )

