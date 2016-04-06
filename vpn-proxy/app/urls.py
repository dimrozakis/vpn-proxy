from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.tunnels, name='tunnels'),
    # /interface_id/target_IP/target_port/
    url(r'(?P<tunnel_id>[0-9]+)/forwardings/'
        r'(?P<target>([0-9]{1,3}.){3}[0-9]{1,3})/'
        r'(?P<port>[0-9]+)/$', views.connection, name='connection'),
    # ping command
    # in case no target is provided, the VPN endpoint will be probed
    url(r'(?P<tunnel_id>[0-9]+)/ping/(?P<target>(([0-9]{1,3}.){3}[0-9]{1,3})?)'
        r'/$', views.ping, name='ping'),
    url(r'(?P<tunel_id>[0-9]+)/$', views.tunnel, name='tunnel'),
    url(r'(?P<tunel_id>[0-9]+)/client_script/$', views.script, name='script'),

]
