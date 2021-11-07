import json

from django.http import HttpResponseBadRequest
from django.utils.deprecation import MiddlewareMixin


class PutParsingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        self.process_request(request)

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    def process_request(self, request):
        if request.method == 'PUT' and request.content_type != 'application/json':
            if hasattr(request, '_post'):
                del request._post
                del request._files
            try:
                request.method = 'POST'
                request._load_post_and_files()
                request.method = 'PUT'
            except AttributeError as e:
                request.META['REQUEST_METHOD'] = 'POST'
                request._load_post_and_files()
                request.META['REQUEST_METHOD'] = 'PUT'

            request.PUT = request.POST


class DeleteParsingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        self.process_request(request)

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    def process_request(self, request):
        if request.method == 'DELETE' and request.content_type != 'application/json':
            if hasattr(request, '_post'):
                del request._post
                del request._files
            try:
                request.method = 'POST'
                request._load_post_and_files()
                request.method = 'DELETE'
            except AttributeError as e:
                request.META['REQUEST_METHOD'] = 'POST'
                request._load_post_and_files()
                request.META['REQUEST_METHOD'] = 'DELETE'

            request.DELETE = request.POST


class JSONParsingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (request.method == 'PUT' or request.method == 'POST') and request.content_type == 'application/json':
            try:
                request.JSON = json.loads(request.body)
            except ValueError as ve:
                return HttpResponseBadRequest('unable to parse JSON data. Error : {0}'.format(ve))
