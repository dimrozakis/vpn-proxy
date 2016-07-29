from __future__ import unicode_literals

import random
import logging

from netaddr import IPAddress, IPNetwork, IPSet

from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.conf import settings

from .tunnels import start_tunnel, stop_tunnel, gen_key
from .tunnels import get_conf, get_client_conf, get_client_script
from .tunnels import add_iptables, del_iptables, add_fwmark, del_fwmark


IFACE_PREFIX = settings.IFACE_PREFIX
SERVER_PORT_START = settings.SERVER_PORT_START
ALLOWED_VPN_ADDRESSES = settings.ALLOWED_HOSTS
EXCLUDED_VPN_ADDRESSES = settings.EXCLUDED_HOSTS

log = logging.getLogger(__name__)


def choose_ip(routable_cidrs, excluded_cidrs=[],
              reserved_cidrs=EXCLUDED_VPN_ADDRESSES, client_addr=''):
    """
    Find available IP addresses for both sides of a VPN Tunnel (client &
    server) based on a list of available_cidrs. This method iterates over the
    CIDRs contained in ALLOWED_VPN_ADDRESSES, while excluding the lists of
    routable_cidrs, excluded_cidrs, and reserved_cidrs.
    :param routable_cidrs: the CIDRs that are to be routed over the
    particular VPN Tunnel
    :param excluded_cidrs: an optional CIDRs list provided by the end user
    in order to be excluded from the address allocation process
    :param reserved_cidrs: CIDRs reserved for local usage
    :param client_addr: since the client IP is allocated first, the client_addr
    is used to attempt to pick an adjacent IP address for the server side.
    Alternatively, this is an empty string
    :return: a private IP address
    """
    exc_nets = routable_cidrs + excluded_cidrs + reserved_cidrs
    # make sure the exc_nets list does not contain any empty strings
    exc_nets = [exc_net for exc_net in exc_nets if exc_net]
    # a list of unique, non-overlapping supernets (to be excluded)
    exc_nets = IPSet(exc_nets).iter_cidrs()
    for network in ALLOWED_VPN_ADDRESSES:
        available_cidrs = IPSet(IPNetwork(network))
        for exc_net in exc_nets:
            available_cidrs.remove(exc_net)
        if not available_cidrs:
            continue
        for cidr in available_cidrs.iter_cidrs():
            first, last = cidr.first, cidr.last
            if client_addr:
                address = IPAddress(client_addr) + 1
            else:
                address = IPAddress(random.randrange(first + 1, last))
            for _ in xrange(first + 1, last):
                if address not in cidr or address == cidr.broadcast:
                    address = cidr.network + 1
                try:
                    Tunnel.objects.get(Q(client=str(address)) |
                                       Q(server=str(address)))
                    address += 1
                except Tunnel.DoesNotExist:
                    return str(address)


def check_ip(addr):
    """Verify that the server/client IP is valid"""
    addr = IPAddress(addr)
    if addr.version != 4 or not addr.is_private():
        raise ValidationError("Only private IPv4 networks are supported.")


def pick_port(_port):
    """Find next available port based on Forwarding.
    This function is used directly by views.py"""
    for _ in xrange(60000):
        try:
            Forwarding.objects.get(loc_port=_port)
            _port += 1
        except Forwarding.DoesNotExist:
            return _port


class BaseModel(models.Model):
    """Abstract base model to be used by Tunnel and Forwarding"""

    active = models.BooleanField(default=True)
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
        for forwarding in self.forwarding_set.all():
            forwarding.reset()

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
        return 'Local port %s via %s -> %s' % (self.port, self.tunnel.name,
                                               self.destination)

    def to_dict(self):
        return {
            'id': self.id,
            'dst_addr': self.dst_addr,
            'dst_port': self.dst_port,
            'loc_port': self.loc_port,
            'tunnel_id': self.tunnel.id,
            'tunnel_name': self.tunnel.name,
            'r_table': self.tunnel.rtable
        }
