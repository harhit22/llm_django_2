# your_project/middleware.py
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseBadRequest

class IgnoreDisallowedHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except DisallowedHost:
            return HttpResponseBadRequest("Invalid host header.")

