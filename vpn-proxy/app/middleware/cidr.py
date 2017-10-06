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

    def process_request(self, request):

        # Get the HTTP host from the request headers.
        host = request.META['REMOTE_ADDR']

        host = netaddr.IPAddress(host)
        cidrs = [netaddr.IPNetwork(cidr) for cidr in settings.SOURCE_CIDRS]

        for cidr in cidrs:
            if host in cidr:
                return
        log.critical('Connection attempt from unauthorized source %s', host)
        raise Http404
