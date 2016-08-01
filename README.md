#IRCapp (code by MrJ, design by Schickele)

##IRCapp is a small highly user friendly, cross-platform (Linux, Windows, Mac) download application for those who don't have the time to bother.

#Installation
Download at : <https://sourceforge.net/projects/ircapp/files/>

##Windows
Simply download and execute the setup.exe file

##Unix
There are currently two .deb files available.

*   FULL Version :  
    Use this version if you do not program python and didn't install any of the following packages (this is the dependency list):      
    
    *   irc
    *   requests
    *   cherrypy
    *   django 1.8.5
    *   pytz
    *   rarfile
    *   miniupnpc
    *   unrar
    *   tk
    
    If you have these packages, there might be an error during the installation (file overwrite).
    Install with:          
    
        sudo dpkg -i IRCapp_2.0_full.deb

*   MIN Version :  
    Use this version in any other case. To install, run:         
     
        sudo apt-get install python3-pip python3-tk
        sudo pip3 install django==1.8.5 irc requests cherrypy pytz miniupnpc
        sudo dpkg -i IRCapp_2.0_min.deb
*   In case you choose to clone the source code, for instance if you implement a server, you should run :

        sudo apt-get install unrar python3-tk       
        sudo pip3 install django==1.8.5 irc requests cherrypy pytz rarfile miniupnpc
##OSX
I'm currently trying to get a Mac and will create a Mac distribution ASAP !

##Contact
ircappwebmaster@gmail.com

###To do's  
A few major things still need to be done:  

*   Add OSX distribution
*   Add SSL support

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


