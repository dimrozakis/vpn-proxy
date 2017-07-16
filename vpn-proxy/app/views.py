import logging


from django.http import HttpResponse
from django.http import JsonResponse as _JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Tunnel, Forwarding
from .models import choose_ip, pick_port

import subprocess
import pingparser


log = logging.getLogger(__name__)


class JsonResponse(_JsonResponse):
    def __init__(self, data, **kwargs):
        kwargs['safe'] = False
        kwargs['json_dumps_params'] = {'indent': 4}
        super(JsonResponse, self).__init__(data, **kwargs)


@require_http_methods(['GET', 'POST'])
def tunnels(request):
    if request.method == 'POST':
        params = {}
        cidrs = request.POST.getlist('cidrs')
        excluded_cidrs = request.POST.getlist('excluded', [])
        client = choose_ip(cidrs, excluded_cidrs)
        params['client'] = client
        params['server'] = choose_ip(cidrs, excluded_cidrs, client_addr=client)
        if 'proto' in request.POST:
            params['protocol'] = request.POST['proto']
        tun = Tunnel(**params)
        tun.save()
        return JsonResponse(tun.to_dict())
    return JsonResponse(map(Tunnel.to_dict, Tunnel.objects.all()))


@require_http_methods(['GET', 'POST', 'DELETE'])
def tunnel(request, tunel_id):
    tun = get_object_or_404(Tunnel, pk=tunel_id)
    if request.method == 'POST':
        tun.enable()
    elif request.method == 'DELETE':
        tun.delete()
        return HttpResponse('OK', status=200)
    return JsonResponse(tun.to_dict())


@require_http_methods(['GET'])
def script(request, tunel_id):
    tun = get_object_or_404(Tunnel, pk=tunel_id)
    return HttpResponse(tun.client_script)


@require_http_methods(['GET'])
def connection(request, tunnel_id, target, port):
    entry = {
        'dst_addr': target,
        'dst_port': int(port),
        'tunnel': get_object_or_404(Tunnel, pk=tunnel_id),
    }
    try:
        # look up db for existing entry in order to avoid duplicates
        forwarding = Forwarding.objects.get(**entry)
        forwarding.enable()
        return HttpResponse(forwarding.port)
    except Forwarding.DoesNotExist:
        try:
            loc_port = pick_port()
        except Exception as exc:
            log.exception(exc)
            return HttpResponse(str(exc), status=409)
        forwarding = Forwarding(loc_port=loc_port, active=False, **entry)
        forwarding.save()
        forwarding.enable()
    return HttpResponse(forwarding.port)


@require_http_methods(['GET'])
def ping(request, tunnel_id, target):
    tunnel = get_object_or_404(Tunnel, pk=tunnel_id)
    if target == '':
        hostname = tunnel.client
    else:
        hostname = target
    pkts = 10
    if request.GET.get('pkts'):
        try:
            pkts = int(request.GET['pkts'])
        except (ValueError, TypeError) as exc:
            log.warning("Couldn't cast pkts param (%s) to int: %r",
                        request.GET['pkts'], exc)

    cmd = ['ping', '-c', str(pkts), '-i', '0.4', '-W', '1', '-q', '-I',
           str(tunnel.name), str(hostname)]
    ping_output = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    ping_parsed = pingparser.parse(ping_output.stdout.read())
    return JsonResponse(ping_parsed)
