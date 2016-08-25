from setuptools import setup


setup(name='ircapp',
      version='2.0',
      author='MrJ',
      description='Simple IRC Client',
      license='MIT',
      url='https://github.com/themadmrj/ircapp',
      packages = ['django==1.8.5', 'irc', 'miniupnpc', 'requests', 'cherrypy', 'pytz'],
      entry_points = {
        'gui_scripts' : ['ircapp = ircapp.main:start_ircapp']
      },
      install_requires = [
        'django==1.8.5',
        'irc',
        'requests',
        'miniupnpc',
        'cherrypy>=0.3.6',
        'pytz'
      ]
)

