from __future__ import unicode_literals

import random
import logging

import netaddr

from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.conf import settings

from .tunnels import start_tunnel, stop_tunnel, gen_key
from .tunnels import get_conf, get_client_conf, get_client_script
from .tunnels import add_iptables, del_iptables, add_fwmark, del_fwmark


IFACE_PREFIX = getattr(settings, 'IFACE_PREFIX', 'vpn-proxy-tun')
SERVER_PORT_START = getattr(settings, 'SERVER_PORT_START', 1195)
ALLOWED_VPN_ADDRESSES = getattr(settings, 'ALLOWED_HOSTS', ['192.168.0.0/16',
                                                            '172.16.0.0/12',
                                                            '10.0.0.0/8'])
EXCLUDED_VPN_ADDRESSES = getattr(settings, 'EXCLUDED_HOSTS', [])

log = logging.getLogger(__name__)


def choose_server_ip(addr, networks=ALLOWED_VPN_ADDRESSES):
    """Find an available server IP in the given network (CIDR notation)
    based on the client IP supplied"""
    address = netaddr.IPAddress(addr)
    for network in networks:
        if address in netaddr.IPNetwork(network):
            # start iterating over the CIDR the IP belongs to
            networks.remove(network)
            networks.append(network)
            break
    else:
        raise ValidationError('IP address is outside the supported range')
    for network in reversed(networks):
        cidr = netaddr.IPNetwork(network)
        exc_nets = []
        for exc_net in EXCLUDED_VPN_ADDRESSES:
            if netaddr.IPNetwork(exc_net) in cidr:
                exc_nets.append(netaddr.IPNetwork(exc_net))
        # a list of unique, non-overlapping supernets
        exc_nets = netaddr.IPSet(exc_nets).iter_cidrs()
        for _ in range(cidr.first + 1, cidr.last):
            address += 1
            if address not in cidr or address == cidr.broadcast:
                address = cidr.network + 1
            for exc_net in exc_nets:
                if address in exc_net:
                    address = netaddr.IPAddress(exc_net.last + 1)
            try:
                Tunnel.objects.get(Q(server=str(address)) |
                                   Q(client=str(address)))
            except Tunnel.DoesNotExist:
                return str(address)


def choose_client_ip(networks=ALLOWED_VPN_ADDRESSES):
    """Find an available client IP in one of the available private networks"""
    for network in reversed(networks):
        cidr = netaddr.IPNetwork(network)
        first, last = cidr.first, cidr.last
        address = netaddr.IPAddress(random.randrange(first + 1, last - 1))
        for _ in range(first + 1, last):
            try:
                Tunnel.objects.get(client=str(address))
                address += 1
                if address not in cidr or address == cidr.broadcast:
                    address = cidr.network + 1
            except Tunnel.DoesNotExist:
                return str(address)


def check_ip(addr):
    """Verify that the server/client IP is valid"""
    addr = netaddr.IPAddress(addr)
    if addr.version != 4 or not addr.is_private():
        raise ValidationError("Only private IPv4 networks are supported.")


def pick_port(_port):
    """Find next available port based on Forwarding.
    This function is used directly by views.py"""
    for _ in range(60000):
        try:
            Forwarding.objects.get(loc_port=_port)
            _port += 1
        except Forwarding.DoesNotExist:
            return _port


class BaseModel(models.Model):
    """Abstract base model to be used by Tunnel and Forwarding"""

    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def enable(self, save=True):
        """Apply server configuration"""
        if not self.active:
            self.active = True
            if save:
                self.save()
        self._enable()

    def disable(self, save=True):
        """Remove server configuration"""
        if self.active:
            self.active = False
            if save:
                self.save()
        self._disable()

    def reset(self, save=True):
        """Reapply server configuration based on state"""
        if self.active:
            self.enable(save=save)
        else:
            self.disable(save=save)

    def save(self, *args, **kwargs):
        """Force model validation and reset server configuration"""
        self.full_clean()
        if self.id:
            self.reset(save=False)
            super(BaseModel, self).save(*args, **kwargs)
        else:
            super(BaseModel, self).save(*args, **kwargs)
            self.reset(save=False)

    def delete(self, *args, **kwargs):
        """Remove server configuration before deleting"""
        self.disable(save=False)
        super(BaseModel, self).delete(*args, **kwargs)


class Tunnel(BaseModel):
    server = models.GenericIPAddressField(protocol='IPv4',
                                          validators=[check_ip],
                                          unique=True)
    client = models.GenericIPAddressField(protocol='IPv4',
                                          validators=[check_ip])
    key = models.TextField(default=gen_key, blank=False, unique=True)

    @property
    def name(self):
        return '%s%s' % (IFACE_PREFIX, self.id)

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

    def _enable(self):
        start_tunnel(self)

    def _disable(self):
        stop_tunnel(self)

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

    def delete(self, *args, **kwargs):
        """Disable and delete all forwardings before deleting tunnel"""
        for forwarding in Forwarding.objects.filter(tunnel=self):
            forwarding.delete()
        super(Tunnel, self).delete(*args, **kwargs)


class Forwarding(BaseModel):
    tunnel = models.ForeignKey(Tunnel, on_delete=models.CASCADE)
    dst_addr = models.GenericIPAddressField(protocol='IPv4')
    dst_port = models.IntegerField()
    loc_port = models.IntegerField(unique=True)
    src_addr = models.GenericIPAddressField(protocol='IPv4')

    @property
    def port(self):
        return self.loc_port

    @property
    def destination(self):
        return '%s:%s' % (self.dst_addr, self.dst_port)

    def _enable(self):
        add_iptables(self)
        add_fwmark(self)

    def _disable(self):
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
