from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.tunnels, name='tunnels'),
    url(r'(?P<tunel_id>[0-9]+)/$', views.tunnel, name='tunnel'),
    url(r'(?P<tunel_id>[0-9]+)/client_script/$', views.script, name='script'),
]
