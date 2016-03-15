from __future__ import unicode_literals

import random
import logging

import netaddr

from django.db import models
from django.core.exceptions import ValidationError

from .tunnels import start_tunnel, stop_tunnel, gen_key
from .tunnels import get_conf, get_client_conf, get_client_script
from .tunnels import add_iptables, del_iptables, add_fwmark, del_fwmark


IFACE_PREFIX = 'vpn-proxy-tun'
SERVER_PORT_START = 1195
VPN_ADDRESSES = '172.17.17.0/24'

log = logging.getLogger(__name__)


def chose_server_ip(network=VPN_ADDRESSES):
    """Find an available server IP in the given network (CIDR notation)"""
    network = netaddr.IPNetwork(network)
    if network.version != 4 or not network.is_private():
        raise Exception("Only private IPv4 networks are supported.")
    first, last = network.first, network.last
    if first % 2:
        first += 1
    for i in range(20):
        addr = str(netaddr.IPAddress(random.randrange(first, last, 2)))
        print addr
        try:
            Tunnel.objects.get(server=addr)
        except Tunnel.DoesNotExist:
            return addr


def check_server_ip(addr):
    """Verify that the server IP is valid"""
    addr = netaddr.IPAddress(addr)
    if addr.version != 4 or not addr.is_private():
        raise ValidationError("Only private IPv4 networks are supported.")
    if not 0 < addr.words[-1] < 254 or addr.words[-1] % 2:
        raise ValidationError("Server IP's last octet must be even in the "
                              "range [2,254].")


def check_destination_ip(addr):
    """Verify that remote IP belongs to a private host"""
    addr = netaddr.IPAddress(addr)
    if addr.version != 4 or not addr.is_private():
        raise ValidationError("Only private IPv4 networks are supported.")


def pick_port(_port):
    """Find next available port based on Ports.
    This function is used directly by views.py"""
    for _ in range(100):
        try:
            Forwarding.objects.get(loc_port=_port)
            _port += 1
        except Forwarding.DoesNotExist:
            return _port


class Tunnel(models.Model):
    server = models.GenericIPAddressField(protocol='IPv4',
                                          default=chose_server_ip,
                                          validators=[check_server_ip],
                                          unique=True)
    key = models.TextField(default=gen_key, blank=False, unique=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def name(self):
        return '%s%s' % (IFACE_PREFIX, self.id)

    @property
    def client(self):
        if self.server:
            octets = self.server.split('.')
            octets.append(str(int(octets.pop()) + 1))
            return '.'.join(octets)

    @property
    def port(self):
        return (SERVER_PORT_START + self.id - 1) if self.id else None

    @property
    def rtable(self):
        return 'rt_%s' % self.name

    @property
    def rp_filter(self):
        return '/proc/sys/net/ipv4/conf/%s/rp_filter' % self.name

    @property
    def key_path(self):
        return '/etc/openvpn/%s.key' % self.name

    @property
    def conf_path(self):
        return '/etc/openvpn/%s.conf' % self.name

    @property
    def conf(self):
        return get_conf(self)

    @property
    def client_conf(self):
        return get_client_conf(self)

    @property
    def client_script(self):
        return get_client_script(self)

    def start(self):
        if not self.active:
            self.active = True
            self.save()
        start_tunnel(self)

    def stop(self):
        if self.active:
            self.active = False
            self.save()
        stop_tunnel(self)

    def reset(self):
        if self.active:
            self.start()
        else:
            self.stop()

    def __str__(self):
        return '%s %s -> %s (port %s)' % (self.name, self.server,
                                          self.client, self.port)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'server': self.server,
            'client': self.client,
            'port': self.port,
            'key': self.key,
            'active': self.active,
        }

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Tunnel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.stop()
        super(Tunnel, self).delete(*args, **kwargs)


class Forwarding(models.Model):
    src_addr = models.GenericIPAddressField(protocol='IPv4')
    dst_addr = models.GenericIPAddressField(protocol='IPv4',
                                            validators=[check_destination_ip])
    dst_port = models.IntegerField()
    loc_port = models.IntegerField(unique=True)
    tunnel = models.ForeignKey(Tunnel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def port(self):
        return self.loc_port

    @property
    def destination(self):
        return '%s:%s' % (self.dst_addr, self.dst_port)

    def enable(self):
        add_iptables(self)
        add_fwmark(self)

    def disable(self):
        del_iptables(self)
        del_fwmark(self)

    def __str__(self):
        return '%s at local port %s via %s -> %s:%s' % (self.src_addr,
                                                        self.port,
                                                        self.tunnel.name,
                                                        self.dst_addr,
                                                        self.dst_port)

    def to_dict(self):
        return {
            'id': self.id,
            'src_addr': self.src_addr,
            'dst_addr': self.dst_addr,
            'dst_port': self.dst_port,
            'dst_pair': self.destination,
            'loc_port': self.loc_port,
            'tunnel_id': self.tunnel.id,
            'tunnel_name': self.tunnel.name,
            'r_table': self.tunnel.rtable
        }

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Forwarding, self).save(*args, **kwargs)
        return self.id

    def delete(self, *args, **kwargs):
        self.disable()
        super(Forwarding, self).delete(*args, **kwargs)
