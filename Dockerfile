# ircapp
#
# BUILD: docker build --no-cache --rm -t ircapp .
# RUN:   docker run --restart="unless-stopped" --name ircapp -p 127.0.0.1:8083:8020 -v $DB_ROOT:/root/.IRCapp -v $DOWNLOAD_ROOT:/root/Downloads --detach=true ircapp 

FROM phusion/baseimage:0.9.15

# Use baseimage-docker's init system.
CMD ["/sbin/my_init"]

# IRCapp
RUN apt-get update && apt-get install -y \
    python3-pip

RUN pip3 install django==1.8.5 irc requests cherrypy pytz rarfile
COPY . /ircapp

# Create DB directory
RUN mkdir $HOME/.IRCapp

# Fixup timezone, if necessary.
RUN cd /ircapp; sed -i "/^timezone.*/c\timezone = $(cat /etc/timezone)" config.ini

# Do not run in debug mode, if necessary.
RUN cd /ircapp; sed -i "/^DEBUG = True/c\DEBUG = False" settings.py

# Listen on all public interfaces, localhost not available to container host.
RUN cd /ircapp; sed -i "/^ip_address = 127.0.0.1/c\ip_address = 0.0.0.0" config.ini

# Copy runit entry (required by phusion baseimage)
RUN mkdir /etc/service/ircapp
ADD ircapp.sh /etc/service/ircapp/run
RUN chmod 755 /etc/service/ircapp/run

# Set the Path for Python
ENV PYTHONPATH=/ircapp

# Set the path for ircapp.sh
ENV IRCAPP_HOME=/ircapp

EXPOSE 8020

# Clean up APT when done.
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

