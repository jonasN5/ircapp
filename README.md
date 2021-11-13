# IRCApp

## IRCApp is a small educational project which I've carried out to play around with the irc protocol and learn how to distribute a python application. IRCApp is only meant to access open-source content.

# Installation

## Windows

Simply download and execute the `setup.exe` file located in the `dist` folder.

## Unix

* To install, first download `ircapp_3.0.tar.gz` located in the `dist` folder, then run:

      sudo apt-get install python3-pip
      pip3 install ircapp_3.0.tar.gz
* To uninstall, run: `pip3 uninstall ircapp`.

## OSX

Same as Unix but you should really consider trading your mac for a pc.

## Local setup
In case you choose to clone the source code, for instance if you implement a server, you should:
* Cd into the project dir
* Clone the repo into an `ircapp` folder
* Run `python venv venv` followed by `source venv/bin/activate` or `venv\Scripts\activate` under Windows
* Run `python pip3 -r ircapp/requirements.txt`

Windows only goodies: if `pip install miniupnp` fails, proceed as follows:
* Download the right wheel depending on the python version from https://ci.appveyor.com/project/miniupnp/miniupnp
* Run `pip install {{thewheel}}`
* Then copy the `miniupnpc.dll` file into the python \Scripts directory (where the python exe resides)

## Contact

https://github.com/themadmrj/ircapp/issues

### Changelog 3.0.0:

I basically completely rewrote the backend which was very poorly written since I was only starting to program.
Major fixes:
* Set a new default search engine
* Added server SSL connection
* Added reverse DCC support
* Fixed an issue where the connection would drop because the socket package acknowledgments would sometimes be sent in the wrong order

### Changelog 2.0.3 (since 2.0):

* Fix: clicking on the file name in the download now properly opens the file location
* Fix: displays an error when trying to change the download directory while downloading
* Fix: added a download_directory to the config.ini, to be used in case the GUI doesn't work properly (couldn't yet find
  why)
* Fix: no more error when searching for a file while no directory was set
* Fix: minor tweak on the cancel system to improve it's reactivity
* Fix: no more problem on the linux package, distribution package is now harmonized cross system

### Changelog 2.0 (since 1.1.1):

* Add: Direct File Transfer (you can now send any file to any IRCapp user)
* Add: multiple simultaneous downloads
* Add: queue option to optimize multiple simultaneous downloads
* Add: documentation (you can always add more, but I already cleaned up the mess quite a lot)
* Change: queue management is now handle server side, it should be less unstable than in the previous version
* Change: if IRCapp is already running and you run it again, a new browser tab will be displayed to IRCapp's index page
* Change: upon restarting IRCapp (with the button), no new tab will be opened; the initial tab will refresh itself
* Change: the Quick Download option now uses more servers to work more often
* Change: the download directory is now selected via a menu
* A few other things probably too...
