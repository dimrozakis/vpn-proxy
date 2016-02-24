from django.http import HttpResponse
from django.http import JsonResponse as _JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Tunnel


class JsonResponse(_JsonResponse):
    def __init__(self, data, **kwargs):
        kwargs['safe'] = False
        kwargs['json_dumps_params'] = {'indent': 4}
        super(JsonResponse, self).__init__(data, **kwargs)


@require_http_methods(['GET', 'POST'])
def tunnels(request):
    if request.method == 'POST':
        params = {}
        if 'server' in request.POST:
            params['server'] = request.POST['server']
        tun = Tunnel(**params)
        tun.save()
        return JsonResponse(tun.to_dict())
    return JsonResponse(map(Tunnel.to_dict, Tunnel.objects.all()))


@require_http_methods(['GET', 'POST'])
def tunnel(request, tunel_id):
    tun = get_object_or_404(Tunnel, pk=tunel_id)
    if request.method == 'POST':
        tun.start()
    return JsonResponse(tun.to_dict())


@require_http_methods(['GET'])
def script(request, tunel_id):
    tun = get_object_or_404(Tunnel, pk=tunel_id)
    return HttpResponse(tun.client_script)
