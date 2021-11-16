import datetime
import time

from django.db import models
from django.forms.models import model_to_dict
from django.utils.timezone import localtime
from django.utils.timezone import now as utcnow


class BaseModel(models.Model):
    """Simple class to expose objects (and avoid PyCharm markings)."""
    objects = models.Manager()

    class Meta:
        abstract = True


class FormatableModel(BaseModel):
    filename = models.CharField(max_length=200)
    size = models.IntegerField(null=True)

    class Meta:
        abstract = True

    def update(self, **kwargs):
        self.__dict__.update(kwargs)
        self.save()

    def format(self) -> dict:
        """Transform the object into a json usable by the html template."""
        _dict = model_to_dict(self)
        if self.size:
            # Format the raw size
            _dict['size_str'] = self.format_number(raw_bytes=self.size)
        return _dict

    @staticmethod
    def format_number(raw_bytes: int) -> str:
        """Format bytes into the corresponding unit as a string."""
        if not raw_bytes:
            return f'0 kB'
        if raw_bytes >= 1000 ** 3:
            return f'{str(round(raw_bytes / (1000 ** 3), 2))} GB'
        elif raw_bytes >= 1000 ** 2:
            return f'{str(int(raw_bytes / (1000 ** 2)))} MB'
        else:
            return f'{str(int(raw_bytes / 1000))} kB'


class Status:
    CONNECTING = 'Connecting to server...'
    WAITING = 'Waiting for package (in queue)...'
    STARTING = 'Starting download...'
    DOWNLOADING = 'Downloading...'
    RESUMING = 'Resuming download...'
    EXTRACTING = 'Extracting...'
    DOWNLOADED = 'Downloaded'
    DOWNLOADED_AND_EXTRACTED = 'Downloaded and extracted properly'
    INTERRUPTED = 'Interrupted'
    SERVER_CONNECTION_ERROR = 'Error during server connection'
    CONNECTION_ERROR = 'Peer connection error'
    FILE_TRANSFER_ERROR = 'Error during file transfer'
    INVALID_PACK_NUMBER = 'Invalid pack number'
    DEAD_LINK = 'Dead link from the search engine'

    @staticmethod
    def waiting_for_seconds(seconds: int):
        return f'Requesting pack at:{utcnow() + datetime.timedelta(seconds=seconds)}'

    @staticmethod
    def connecting_with_attempts(attempts: int):
        return f'Connecting to server... ({attempts})'


class DownloadHistory(FormatableModel):
    status = models.CharField(max_length=200)
    duration = models.DurationField(default=datetime.timedelta())
    attempts = models.IntegerField(default=1)
    end_date = models.DateTimeField(auto_now=True)

    @property
    def average(self):
        """Average download speed"""
        if self.duration.total_seconds() == 0:
            return 0
        else:
            return round((self.size / 1000) / self.duration.total_seconds(), 0)

    def format(self):
        """Transform the object into a json usable by the html template."""
        _dict = super().format()
        _dict['average'] = self.average

        if self.end_date:
            # Format the date
            if localtime(self.end_date).date() == utcnow().date():
                _dict['end_date'] = localtime(self.end_date).time().strftime('%H:%M:%S')
            elif localtime(self.end_date).year == utcnow().year:
                _dict['end_date'] = localtime(self.end_date).strftime('%d %b %H:%M:%S')
            else:
                _dict['end_date'] = localtime(self.end_date).strftime('%Y %d %b %H:%M:%S')
        if self.duration:
            # Format the duration
            s = self.duration.total_seconds()
            if s < 60:
                _dict['duration'] = str(int(s)) + 's'
            elif s < 3600:
                _dict['duration'] = str(int(s / 60)) + 'm' + str(int(s % 60)) + 's'
            else:
                _dict['duration'] = str(int(s / 3600)) + 'h' + str(int(s % 3600 / 60)) + 'm' + str(
                    int(s % 3600 % 60)) + 's'
        return _dict


class DownloadQueue(FormatableModel):
    server = models.CharField(max_length=200)
    channel = models.CharField(max_length=200)
    bot = models.CharField(max_length=200)
    package_number = models.IntegerField(null=True)


class DownloadOngoing(FormatableModel):
    status = models.CharField(max_length=200)
    speed = models.IntegerField(null=True)  # In bytes/second
    received_bytes = models.IntegerField(null=True)
    progress = models.IntegerField(null=True)
    eta = models.DateTimeField(null=True)
    time_left = models.IntegerField(null=True)
    active = models.BooleanField(default=True)
    canceled = models.BooleanField(default=False)
    duration = models.DurationField(default=datetime.timedelta())
    # this part is used in case the download was interrupted and has to be resumed
    server = models.CharField(max_length=200)
    channel = models.CharField(max_length=200)
    bot = models.CharField(max_length=200)
    package_number = models.IntegerField(null=True)
    attempts = models.IntegerField(null=True)

    @property
    def percentage(self) -> int:
        if self.received_bytes and self.size:
            return int(float(self.received_bytes) / float(self.size) * 100)
        return 0

    def update_bytes(self, new_bytes: int):
        """
        Update received_bytes and calculate speed, time_left and eta each second.
        Also increment the duration field each second.
        """
        self.status = Status.DOWNLOADING

        if not self.received_bytes:
            self.received_bytes = 0
        if not hasattr(self, 'last_bytes'):
            self.last_bytes = self.received_bytes
            self.last_update = utcnow() - datetime.timedelta(seconds=2)
        self.received_bytes += new_bytes
        self.progress = self.percentage
        if self.last_update < utcnow() - datetime.timedelta(seconds=1):
            self.speed = self.received_bytes - self.last_bytes  # Speed in bytes/s since we calculate it each second
            if self.speed != 0:
                self.time_left = (self.size - self.received_bytes) / self.speed
            else:
                self.time_left = 99999
            self.eta = utcnow() + datetime.timedelta(seconds=self.time_left)

            self.duration = datetime.timedelta(seconds=self.duration.total_seconds() + 1)

            self.save()
            self.last_update = utcnow()
            self.last_bytes = self.received_bytes

    def add_to_queue(self) -> DownloadQueue:
        queue_obj = DownloadQueue(filename=self.filename, size=self.size, server=self.server,
                                  channel=self.channel, bot=self.bot, package_number=self.package_number)
        queue_obj.save()
        return queue_obj

    def format(self):
        """Transform the object into a json usable by the html template.

        We also add a couple of additional computed fields:
        -eta: calculated date of the end of the download
        -time_left: how much time is left until eta
        """
        _dict = super().format()
        if self.speed:
            _dict['speed'] = int(self.speed / 1000)  # Convert bytes/s to kB/s
            # Format eta
            if self.eta:
                if localtime(self.eta).date() == utcnow().date():
                    _dict['eta'] = localtime(self.eta).time().strftime('%H:%M:%S')
                else:
                    _dict['eta'] = localtime(self.eta).time().strftime('%d %b %H:%M:%S')
            else:
                _dict['eta'] = ''
            # Format time_left
            if self.time_left > 3600:
                _dict['time_left'] = time.strftime('%H h %M min %S sec', time.gmtime(self.time_left))
            elif self.time_left > 60:
                _dict['time_left'] = time.strftime('%M min %S sec', time.gmtime(self.time_left))
            elif self.time_left:
                _dict['time_left'] = time.strftime('%S sec', time.gmtime(self.time_left))
            else:
                _dict['time_left'] = ''
        # Format received_bytes
        _dict['received_bytes_str'] = self.format_number(raw_bytes=self.received_bytes)

        return _dict


class UploadOngoing(FormatableModel):
    status = models.CharField(max_length=200)
    speed = models.IntegerField(null=True)
    progress = models.IntegerField(null=True)
    completed = models.IntegerField(null=True)
    eta = models.DateTimeField(null=True)
    time_left = models.IntegerField(null=True)
    active = models.BooleanField(default=True)
    server = models.CharField(max_length=200)
    username = models.CharField(max_length=200)


class SearchTerm(BaseModel):
    """A string to exclude or that must be contained in the search query's response."""
    text = models.CharField(max_length=200)


class UpnpPort(BaseModel):
    """A port currently mapped."""
    port = models.IntegerField()


class DownloadSettings(BaseModel):
    download_box_state = models.BooleanField(default=True)  # True if the box is visible, False otherwise
    shutdown = models.BooleanField(default=False)
    queue_similar = models.BooleanField(default=True)  # True if similar packages should be enqueued, not downloaded
    restart = models.BooleanField(default=False)
    path = models.CharField(max_length=200)  # The path to the download directory
    priority_choices = [
        ('bluray', 'Maximum (BluRay)'),
        ('1080', 'Excellent (1080p)'),
        ('720', 'Good (720p)'),
        ('hd', 'Normal')
    ]
    priority = models.CharField(max_length=6, choices=priority_choices, default='720')  # QuickDownload setting
    contains = models.ManyToManyField(SearchTerm,
                                      related_name='contained')  # QuickDownload setting
    excludes = models.ManyToManyField(SearchTerm,
                                      related_name='excluded')  # QuickDownload setting

    @property
    def contains_list(self) -> list:
        """Return a list representation of self.contains"""
        return [(obj.id, obj.text) for obj in self.contains.all()]

    @property
    def excludes_list(self) -> list:
        """Return a list representation of self.excludes"""
        return [(obj.id, obj.text) for obj in self.excludes.all()]

    @staticmethod
    def get_object():
        return DownloadSettings.objects.latest('id')
