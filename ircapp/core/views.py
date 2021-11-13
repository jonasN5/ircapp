import json
import subprocess
import sys
import random
import string
from threading import Timer

import cherrypy
import easygui
from django.core.exceptions import ObjectDoesNotExist, BadRequest
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View

from core.forms import *
from core.managers.extraction import FileExtractor
from core.managers.search import get_search_engine, SearchEngineResponseItem
from core.models import *
from core.utils.directory import get_download_directory, get_free_space_mb
from core.utils.logging import get_log_path, log
from core.dispatcher import Dispatcher


def _get_param_or_return_400(kwargs: dict, key: str):
    """Not a view - shortcut function to validate a parameter or return 400 status code."""
    if key in kwargs:
        return kwargs[key]
    raise BadRequest(f'The parameter "{key}" must be provided')


class Index(View):

    def get(self, request, *args, **kwargs):
        """Main view when loading IRC ircapp."""
        _settings = DownloadSettings.get_object()
        context = {
            'directory': get_download_directory(),
            'free_space': get_free_space_mb(),
            'quick_down_value': _settings.priority,
            'contains': _settings.contains_list,
            'excludes': _settings.excludes_list,
            'path_form': PathForm(instance=_settings),
            'down_box': _settings.download_box_state,
        }
        return render(request, 'search.html', context)


class QuickDown(View):

    def post(self, request, *args, **kwargs):
        """Called when clicking the bolt to see if a download can be started immediately.
        :param query: the string to search
        """
        query = _get_param_or_return_400(request.POST, 'query')
        item = get_search_engine().quick_search(query)
        if item:
            # Quick download enabled: download without displaying results.
            return Download().post(request=request, quick_download_item=item)
        else:
            # No match found with the quick download method.
            # Display search results instead.
            return JsonResponse({'redirect': True, 'query': query})


class Download(View):

    def post(self, request, quick_download_item: SearchEngineResponseItem = None, *args, **kwargs):
        """View responsible for processing a normal download request by clicking a search result,
        as opposed to quick_download.
        :param quick_download_item: only used internally by QuickDown
        :param package_info: [filename, size, server, channel, bot, pack_number]
        """
        if quick_download_item:
            q = quick_download_item
            filename, size, server, channel, bot, pack_number = (
                q.filename, q.size, q.network, q.channel, q.bot, q.pack_number)
        else:
            data = _get_param_or_return_400(request.POST, 'package_info')
            filename, size, server, channel, bot, pack_number = json.loads(data)
        return Dispatcher().start_new_download(filename=filename, size=size, server=server, channel=channel, bot=bot,
                                               pack_number=pack_number)


class Monitor(View):

    def get(self, request, *args, **kwargs):
        """Get the updated state of ongoing downloads and if the queue and/or history needs to be updated."""
        response = {'update_elements': False}
        download_ongoing_list = []
        for download_object in DownloadOngoing.objects.all():
            download_ongoing_list.append(download_object.format())
        if download_ongoing_list:
            response['download_ongoing_list'] = download_ongoing_list

        # Check if the GUI needs an update (queue/history)
        if int(request.GET.get('history_count', 0)) != DownloadHistory.objects.count() or (
                int(request.GET.get('queue_count', 0)) != DownloadQueue.objects.count()):
            response['update_elements'] = True

        return JsonResponse(response)


def upload_monitor(request):
    # workaround with time.sleep for a weird problem : first database call fails, maybe needs time to load ?
    pass


class Search(View):

    def get(self, request, *args, **kwargs):
        """Search for the given query on the search engine.
        :param query: str The string to search for
        :param page_number (optional): int The page number
        :param no_quick (optional): bool Whether the request is to do a quick download
        """
        query = _get_param_or_return_400(request.GET, 'query')
        page_number = request.GET.get('page_number', 0)
        no_quick = request.GET.get('no_quick', False)
        _settings = DownloadSettings.get_object()
        context = {
            'directory': get_download_directory(),
            'free_space': get_free_space_mb(),
            'path_form': PathForm(instance=_settings),
            'query': query,
            'no_quick': no_quick,
            'contains': _settings.contains_list,
            'excludes': _settings.excludes_list,
            'down_box': _settings.download_box_state
        }

        try:
            search_engine = get_search_engine()
            response = search_engine.search(query=query, page_number=page_number)
            _json = response.to_json()
            context['results'] = response.results
            context['page_number'] = response.page_number
            context['can_fetch_more_results'] = response.can_fetch_more_results
            if response.is_empty:
                context['message'] = f'No match for “{query}” on the search engine'
        except ConnectionError:
            context['message'] = "Couldn't access the search engine, exiting"

        return render(request, 'results.html', context)


class QuickDownPreferences(View):

    def delete(self, request, *args, **kwargs):
        """Delete a term in 'contains' or 'excludes'.
        :param pk: int The pk of the object to delete
        """
        pk = int(_get_param_or_return_400(request.DELETE, 'pk'))
        SearchTerm.objects.get(pk=pk).delete()
        return HttpResponse('OK', status=204)

    def put(self, request, *args, **kwargs):
        """Update the quick download preferences.
        :param priority (optional): str QuickDownload.priority
        :param contains (optional): str QuickDownloadContains.contains
        :param excludes (optional): str QuickDownloadExcludes.excludes
        """
        _settings = DownloadSettings.get_object()
        if 'priority' in request.PUT:
            _settings.priority = request.PUT['priority']
            _settings.save()
            return HttpResponse('OK')
        elif 'contains' in request.PUT:
            term = SearchTerm.objects.create(text=request.PUT['contains'])
            _settings.contains.add(term)
            return JsonResponse({'id': term.pk, 'text': term.text})
        elif 'excludes' in str(request.PUT):
            term = SearchTerm.objects.create(text=request.PUT['excludes'])
            _settings.contains.add(term)
            return JsonResponse({'id': term.pk, 'text': term.text})


def space(request):
    """Return the free disk space on the hard drive."""
    return JsonResponse(get_free_space_mb(), safe=False)


class DownloadPath(View):

    def post(self, request, *args, **kwargs):
        """Update the download directory."""
        if DownloadOngoing.objects.exists():
            if DownloadOngoing.objects.latest('id').active and DownloadOngoing.objects.latest(
                    'id').status != Status.INTERRUPTED:
                msg = u_('Cannot change the download directory while downloading. Please ' +
                         'wait for your download to finish.')
                return JsonResponse({'error': msg})
        path = easygui.diropenbox()
        if not path:
            # No path chosen
            return HttpResponse()
        _settings = DownloadSettings.get_object()
        _settings.path = path
        _settings.save()
        # root.destroy()
        return JsonResponse({'success': path})


class DownloadDir(View):

    def get(self, request, *args, **kwargs):
        """Open the download destination directory.
        :param pk: int The pk of the DownloadHistory or DownloadOngoing object to open
        :param type: str One of ['history', 'download_ongoing'] to specify which object to check
        """
        pk = _get_param_or_return_400(request.GET, 'pk')
        _type = _get_param_or_return_400(request.GET, 'type')
        base_folder = get_download_directory()
        if base_folder:
            folder_name = base_folder
            if _type == 'history':
                obj = DownloadHistory.objects.get(pk=pk)
                if obj.status == Status.DOWNLOADED_AND_EXTRACTED and '.tar' in FileExtractor.splitext(obj.filename)[1]:
                    folder_name = os.path.join(base_folder, FileExtractor.splitext(obj.filename)[0])
            else:
                obj = DownloadOngoing.objects.get(pk=pk)
                if obj.status == Status.EXTRACTING and '.tar' in FileExtractor.splitext(obj.filename)[1]:
                    folder_name = os.path.join(base_folder, '_UNPACK_' + FileExtractor.splitext(obj.filename)[0])
                elif (obj.status == Status.DOWNLOADED_AND_EXTRACTED and
                      '.tar' in FileExtractor.splitext(obj.filename)[1]):
                    folder_name = os.path.join(base_folder, FileExtractor.splitext(obj.filename)[0])
            if sys.platform == 'win32':
                os.startfile(folder_name)
            else:
                opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                subprocess.call([opener, folder_name])
            return HttpResponse('Successfully opened the directory')
        else:
            return HttpResponse('No directory set to open dir')


def read_log(request):
    """Open the log in a separate tab."""
    log_file = open(get_log_path())
    response = HttpResponse(content=log_file)
    response['Content-Type'] = 'text/plain'
    log_file.close()
    return response


def dcctransfer_information(request):
    nick = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
    pw = ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(12))
    # core.download.xdcc(nick=nick, pw=pw)
    return JsonResponse({'nick': nick, 'password': pw})


# send file feature
def send_file(request):
    nickname = request.GET['nick']
    password = request.GET['pw']
    path = easygui.fileopenbox()
    if not path:
        return HttpResponse("")
    if UploadOngoing.objects.count() > 0:
        # direct filet transfer already ongoing
        return HttpResponse("")
    else:
        # upload_file(path, nickname, password)
        return JsonResponse({'msg': "success"})


class History(View):

    def get(self, request, *args, **kwargs):
        """Return the whole history, in descending order and formatted."""
        prepared_data = [obj.format() for obj in DownloadHistory.objects.order_by("-end_date")]
        return JsonResponse(prepared_data, safe=False)

    def delete(self, request, *args, **kwargs):
        """Delete a single history entry, providing the pk, otherwise delete the whole history.
        :param pk (optional): int The pk of the DownloadHistory object to delete
        """
        pk = request.DELETE.get('pk', None)
        if pk:
            try:
                # Single item from history removed, update database.
                DownloadHistory.objects.get(pk=pk).delete()
                return HttpResponse('Item deleted')
            except ObjectDoesNotExist:
                pass
        else:
            DownloadHistory.objects.all().delete()
        return HttpResponse("OK")


class Queue(View):

    def get(self, request, *args, **kwargs):
        """Return the whole queue, in descending order and formatted."""
        prepared_data = [obj.format() for obj in DownloadQueue.objects.all().order_by("-id")]
        return JsonResponse(prepared_data, safe=False)

    def delete(self, request, *args, **kwargs):
        """Delete a single history entry, providing the pk, otherwise delete the whole history.
        :param pk: int The pk of the DownloadQueue object to delete
        """
        pk = _get_param_or_return_400(request.DELETE, 'pk')
        try:
            # Item from queue removed, update database
            DownloadQueue.objects.get(pk=pk).delete()
            return HttpResponse('Item deleted')
        except ObjectDoesNotExist:
            return HttpResponse('Item already deleted')


class CancelDownload(View):

    def post(self, request, *args, **kwargs):
        """Cancel an ongoing download.
        :param pk: int The pk of the DownloadOngoing object to cancel
        """
        pk = _get_param_or_return_400(request.POST, 'pk')
        try:
            down_obj = DownloadOngoing.objects.get(pk=pk)
            log(f'Canceling {down_obj.filename}')
            Dispatcher().cancel_download(server=down_obj.server, bot=down_obj.bot)
            return HttpResponse('ok')
        except ObjectDoesNotExist:
            return HttpResponse('No item to cancel')


def cancel_upload(request):
    pass
    # up = UploadOngoing.objects.latest("id")
    # botqueue = main.queuedict[up.server + up.username]
    # botqueue.put("cancel")
    # return HttpResponse("upload canceled")


class DownSettings(View):

    def get(self, request, *args, **kwargs):
        """Get the settings (for instance if download box is displayed),
        mainly to redisplay properly when user hits F5"""
        obj = DownloadSettings.get_object()
        data = {
            'down_box': obj.download_box_state,
            'queue_similar': obj.queue_similar,
            'shutdown': obj.shutdown
        }
        return JsonResponse(data)

    def put(self, request, *args, **kwargs):
        """Update the download settings.
        :param down_box (optional): bool DownloadSettings.download_box_state
        :param queue_similar (optional): bool DownloadSettings.queue_similar
        :param shutdown (optional): bool DownloadSettings.shutdown
        """
        obj = DownloadSettings.get_object()
        if 'down_box' in request.PUT:
            obj.download_box_state = int(request.PUT['down_box'])
        elif 'queue_similar' in request.PUT:
            obj.queue_similar = int(request.PUT['queue_similar'])
        elif 'shutdown' in request.PUT:
            obj.shutdown = int(request.PUT['shutdown'])
        obj.save()
        return HttpResponse('OK')


def shutdown_server(request):
    """Shutdown IRCApp."""
    par = request.GET['par']
    if par == 'render':
        return render(request, 'shutdown.html')
    else:
        Dispatcher().shutdown_server()
        return HttpResponse('OK')


def restart_server(request):
    """Restart IRCApp."""
    par = request.GET['par']
    if par == 'render':
        obj = DownloadSettings.get_object()
        obj.restart = True
        obj.save()
        return render(request, 'restart.html')
    elif par == 'respawn':
        return HttpResponse('OK')
    else:
        Dispatcher().stop_all_downloads()
        # We delay the restart command slightly to be able to serve the next static requests
        Timer(0.2, cherrypy.engine.restart).start()
        return HttpResponse('OK')
