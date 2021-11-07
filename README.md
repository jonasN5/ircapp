#IRCapp (code by MrJ, design by Schickele)

##IRCapp is a small highly user friendly, cross-platform (Linux, Windows, Mac) download application for those who don't have the time to bother.

#Installation
Download at : <https://sourceforge.net/projects/ircapp/files/>

##Windows
Simply download and execute the setup.exe file

##Unix
*   To install, run:         
     
        sudo apt-get install python3-pip python3-tk unrar
        sudo pip3 install django irc requests cherrypy pytz miniupnpc
        sudo dpkg -i IRCapp_2.0.3.deb
*   In case you choose to clone the source code, for instance if you implement a server, you should run :

        sudo apt-get install python3-pip python3-tk unrar       
        sudo pip3 install django irc requests cherrypy pytz rarfile miniupnpc
##OSX
I'm currently trying to get a Mac and will create a Mac distribution ASAP !

##Contact
https://github.com/themadmrj/ircapp/issues

###To do's  
A few major things still need to be done:  

* Add OSX distribution
* Add SSL support

###Changelog 2.1.0 :

###Changelog 2.0 (since 1.1.1) :
*   Add: Direct File Transfer (you can now send any file to any IRCapp user)
*   Add: multiple simultaneous downloads
*   Add: queue option to optimize multiple simultaneous downloads
*   Add: documentation (you can always add more, but I already cleaned up the mess quite a lot)
*   Change: queue management is now handle server side, it should be less unstable than in the previous version
*   Change: if IRCapp is already running and you run it again, a new browser tab will be displayed to IRCapp's index page
*   Change: upon restarting IRCapp (with the button), no new tab will be opened; the initial tab will refresh itself
*   Change: the Quick Download option now uses more servers to work more often
*   Change: the download directory is now selected via a menu
*   A few other things probably too...

###Changelog 2.0.3 (since 2.0) :
*   Fix: clicking on the file name in the download now properly opens the file location
*   Fix: displays an error when trying to change the download directory while downloading
*   Fix: added a download_directory to the config.ini, to be used in case the GUI doesn't work properly (couldn't yet find why)
*   Fix: no more error when searching for a file while no directory was set
*   Fix: minor tweak on the cancel system to improve it's reactivity
*   Fix: no more problem on the linux package, distribution package is now harmonized cross system
