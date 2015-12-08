from setuptools import setup


setup(name='ircapp',
      version='1.1',
      author='MrJ',
      author_email='ircappwebmaster@gmail.com',
      description='IRC download application',
      license='MIT',
      url='https://github.com/themadmrj/ircapp',
      packages = ['django>=1.8', 'irc', 'requests', 'cherrypy', 'pytz'],
      entry_points = {
        'gui_scripts' : ['ircapp = ircapp.main:start_ircapp']
      },
      install_requires = [
        'django>=1.8',
        'irc',
        'requests',
        'cherrypy>=0.3.6',
        'pytz'
      ]
)

