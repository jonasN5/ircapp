from django import forms
from ircapp.models import Download_Path, Download_Ongoing, Quick_Download
from django.utils.translation import ugettext_lazy as u_
import os

class PathForm(forms.ModelForm):
    class Meta:
        model = Download_Path
        fields = ['download_path']
        
    def clean_download_path(self):
        download_path = self.cleaned_data['download_path']
        if Download_Ongoing.objects.all().count() > 0:
            if Download_Ongoing.objects.latest('id').active == True and Download_Ongoing.objects.latest('id').status != "Interrupted":
                raise forms.ValidationError(u_('Cannot change the download directory while downloading. Please wait for your download to finish.'), code='invalid')
        if download_path:
            if not os.path.exists(download_path):
                raise forms.ValidationError(u_('Indicated path could not be found. Please make sure you indicate the full directory path.'), code='invalid')
        return download_path


