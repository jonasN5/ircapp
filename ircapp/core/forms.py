from django import forms
from core.models import DownloadSettings, DownloadOngoing
from django.utils.translation import ugettext_lazy as u_
import os


class PathForm(forms.ModelForm):
    class Meta:
        model = DownloadSettings
        fields = ['path']

    def clean_download_path(self):
        download_path = self.cleaned_data['path']
        if DownloadOngoing.objects.all().count() > 0:
            if DownloadOngoing.objects.latest('id').active and DownloadOngoing.objects.latest(
                    'id').status != "Interrupted":
                raise forms.ValidationError(
                    u_('Cannot change the download directory while downloading. Please wait for your download to finish.'),
                    code='invalid')
        if download_path:
            if not os.path.exists(download_path):
                raise forms.ValidationError(
                    u_('Indicated path could not be found. Please make sure you indicate the full directory path.'),
                    code='invalid')
        return download_path
