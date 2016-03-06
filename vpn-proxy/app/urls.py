from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.tunnels, name='tunnels'),
    url(r'(?P<tunel_id>[0-9]+)/$', views.tunnel, name='tunnel'),
    url(r'(?P<tunel_id>[0-9]+)/client_script/$', views.script, name='script'),
    # /source_IP/target_IP/target_port/interface_id/
    url(  # r'(?P<peer>((2[0-5]|1[0-9]|[0-9])?[0-9]\.){3}((2[0-5]|1[0-9]|[0-9])?[0-9]))/'
        r'(?P<target>((2[0-5]|1[0-9]|[0-9])?[0-9]\.){3}((2[0-5]|1[0-9]|[0-9])?[0-9]))/'
        r'(?P<port>[0-9]+)/'
        r'(?P<tunel_id>[0-9]+)/$', views.connection, name='connection'),
]