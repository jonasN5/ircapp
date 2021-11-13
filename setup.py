import sys, os
from setuptools import setup, find_packages
from ircapp.ircapp.version import __version__

data_files = [
    (os.path.join('share', 'applications'), ['ircapp.desktop']),
    (os.path.join('share', 'icons', 'hicolor', 'scalable', 'apps'),
     ['ircapp/core/static/ircapp_bolt.svg'])
]

packages = ['django', 'irc', 'requests', rarfile, 'cherrypy', 'miniupnpc', 'easygui', 'names', 'dataclasses_json']

setup(
    name='IRCApp',
    version=__version__,
    description='Simple IRC app based on irclib',
    author='MrJ',
    data_files=data_files,
    license='MIT',
    url='https://github.com/themadmrj/ircapp',
    packages=find_packages(exclude=['*test*']),
    entry_points={
        'gui_scripts': ['ircapp = ircapp.main:start_app']
    },
    include_package_data=True,
    install_requires=packages
)
