import netaddr
import logging

from django.http import Http404
from django.conf import settings


log = logging.getLogger(__name__)


class CidrMiddleware(object):
    """A middleware that filters requests based on their origin.

    This middleware plays the role of settings.ALLOWED_HOSTS, while it also
    allows filtering to take place based on ranges of IP addresses given in
    CIDR notation.

    The host's IP address is verified against the list of networks provided
    in settings.SOURCE_CIDRS. In case of no match, an HTTP 404 status code
    is returned.

    See https://docs.djangoproject.com/en/1.11/ref/settings/#allowed-hosts

    """

    def __init__(self, get_response):
        # One-time configuration & initialization, when the web server starts.
        self.get_response = get_response

        self.cidrs = [
            netaddr.IPNetwork(cidr) for cidr in settings.SOURCE_CIDRS
        ]

    def __call__(self, request):
        # Get the source IP address from the request headers.
        host = request.META['REMOTE_ADDR']
        for cidr in self.cidrs:
            if netaddr.IPAddress(host) in cidr:
                return self.get_response(request)
        log.critical('Connection attempt from unauthorized source %s', host)
        raise Http404()
