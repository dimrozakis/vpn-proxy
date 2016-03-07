from __future__ import unicode_literals

import random
import logging

import netaddr

from django.db import models
from django.core.exceptions import ValidationError

from .tunnels import start_tunnel, stop_tunnel, gen_key
from .tunnels import get_conf, get_client_conf, get_client_script
from .tunnels import run


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
	"""Find next available port based on Ports. This function is used directly by views.py"""
	for _ in range(100):
		try:
			Ports.objects.get(loc_port=_port)
			_port += 1
		except Ports.DoesNotExist:
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


class Ports(models.Model):
	src_addr = models.GenericIPAddressField(protocol='IPv4')
	dst_addr = models.GenericIPAddressField(protocol='IPv4', validators=[check_destination_ip])
	dst_port = models.IntegerField()
	tunel_id = models.IntegerField()
	loc_port = models.IntegerField(unique=True)
	created_at = models.DateTimeField(auto_now_add=True)

	@property
	def tunnel(self):
		return '%s%s' % (IFACE_PREFIX, self.tunel_id)

	@property
	def port(self):
		return self.loc_port

	@property
	def rtable(self):
		return 'rt_%s' % self.tunnel

	@property
	def destination(self):
		return '%s:%s' % (self.dst_addr, self.dst_port)

	def __str__(self):
		return '%s at local port %s via %s -> %s:%s' % (self.src_addr, self.port, self.tunnel, self.dst_addr, self.dst_port)

	def to_dict(self):
		return {
			'id': self.id,
			'src_addr': self.src_addr,
			'dst_addr': self.dst_addr,
			'dst_port': self.dst_port,
			'dst_pair': self.destination,
			'tunnel_id': self.tunel_id,
			'tunnel_name': self.tunnel,
			'loc_port': self.loc_port,
			'r_table': self.rtable
		}

	def forward(self, mode, **new_record):
		modes = {
			'add': '-A',
			'delete': '-D'
		}
		for key in modes.iterkeys():
			if key == mode:
				job = modes[key]
				# mangle incoming packets based on local port
				# mangle table is traversed before nat in every chain
				run(['sudo', 'iptables', '-t', 'mangle', job, 'PREROUTING', '-p', 'tcp',
				     '--destination-port', str(new_record['loc_port']),
				     '-j', 'MARK', '--set-mark', str(new_record['tunnel_id'])])
				# DNAT incoming packets in order to force forwarding --> private host (IP, PORT)
				run(['sudo', 'iptables', '-t', 'nat', job, 'PREROUTING', '-p', 'tcp',
				     '--destination-port', str(new_record['loc_port']),
				     '-j', 'DNAT', '--to-destination', str(new_record['dst_pair'])])
				# MASQUERADE packets routed via the virtual interface
				run(['sudo', 'iptables', '-t', 'nat', job, 'POSTROUTING', '-p', 'tcp', '-o', str(new_record['tunnel_name']),
				     '-d', str(new_record['dst_addr']), '--destination-port', str(new_record['dst_port']),
				     '-j', 'MASQUERADE'])
				# point marked packets to the corresponding routing table as created during `openvpn start`
				run(['sudo', 'ip', 'rule', str(key), 'fwmark', str(new_record['tunnel_id']), 'table', str(new_record['r_table'])])

	def save(self, *args, **kwargs):
		"""Insert forwarding rules as soon as entry is saved"""
		self.full_clean()
		super(Ports, self).save(*args, **kwargs)
		new_record = self.to_dict()
		self.forward('add', **new_record)
		return self.id

	def delete(self, *args, **kwargs):
		"""Delete forwarding rules along entry removal"""
		old_record = self.to_dict()
		self.forward('delete', **old_record)
		super(Ports, self).delete(*args, **kwargs)