#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"

if [ -z "$WEB_SOCKET" ]; then
    echo "Please enter IP or IP:PORT (private) for the webserver:"
    read WEB_SOCKET
    echo
fi

if [ -z "$VPN_IP" ]; then
    echo "Please enter public IP address for the VPN server:"
    read VPN_IP
    echo
fi

if [ -z "$SOURCE_CIDRS" ]; then
    echo "Please enter the CIDR(s) of the source host(s):"
    read SOURCE_CIDRS
    echo
fi

if [ -z "$IN_IFACE" ]; then
    echo "Please enter the lan interface of the server:"
    read IN_IFACE
    echo
fi

echo "Installing vpn-proxy from $DIR."
echo "Webserver will be listening to $WEB_SOCKET."
echo "VPN server will be listening to $VPN_IP."
echo "VPN server will be forwarding requests originating from $SOURCE_CIDRS."
echo

set -ex

apt-get update -q
apt-get install -yq --no-install-recommends \
    python python-pip openvpn uwsgi uwsgi-plugin-python

pip install -U pip
pip install -U django netaddr ipython

echo "VPN_SERVER_REMOTE_ADDRESS = \"$VPN_IP\"" > $DIR/vpn-proxy/conf.d/0000-vpn-ip.py
echo "SOURCE_CIDRS = \"$SOURCE_CIDRS\"" | tr -s ' ' > $DIR/vpn-proxy/conf.d/0001-src-cidrs.py
echo "IN_IFACE = \"$IN_IFACE\"" > $DIR/vpn-proxy/conf.d/0002-lan-iface.py

$DIR/vpn-proxy/manage.py migrate
$DIR/vpn-proxy/manage.py autosuperuser

mkdir -p $DIR/tmp

cat > /etc/uwsgi/apps-available/vpn-proxy.ini << EOF
[uwsgi]

chdir = $DIR/vpn-proxy
module = project.wsgi

http = $WEB_SOCKET
processes = 4

master = true
vacuum = true

uid = root
gid = root
EOF
cat /etc/uwsgi/apps-available/vpn-proxy.ini
ln -sf /etc/uwsgi/apps-available/vpn-proxy.ini /etc/uwsgi/apps-enabled/
systemctl restart uwsgi
systemctl status uwsgi

sed -i 's/^#\?\s*net.ipv4.ip_forward\s*=\s*.*$/net.ipv4.ip_forward=1/' /etc/sysctl.conf
grep '^net.ipv4.ip_forward=1$' /etc/sysctl.conf || \
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
sysctl -p
