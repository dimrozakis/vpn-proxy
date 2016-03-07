from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.tunnels, name='tunnels'),
    # /target_IP/target_port/interface_id/
    url(r'(?P<target>([0-9]{1,3}.){3}[0-9]{1,3})/'
        r'(?P<port>[0-9]+)/'
        r'(?P<tunel_id>[0-9]+)/$', views.connection, name='connection'),
    url(r'(?P<tunel_id>[0-9]+)/$', views.tunnel, name='tunnel'),
    url(r'(?P<tunel_id>[0-9]+)/client_script/$', views.script, name='script'),
]