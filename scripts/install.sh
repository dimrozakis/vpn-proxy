#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"

if [ -z "$SOCKET" ]; then
    echo "Please enter IP or IP:PORT (private) for the webserver:"
    read SOCKET
    echo
fi

echo "Installing vpn-proxy from $DIR, will listen to $SOCKET"
echo

set -ex

apt-get update -q
apt-get install -yq --no-install-recommends \
    python python-pip openvpn uwsgi uwsgi-plugin-python

pip install -U pip
pip install -U django netaddr ipython

$DIR/vpn-proxy/manage.py migrate
$DIR/vpn-proxy/manage.py autosuperuser

mkdir -p $DIR/tmp

cat > /etc/uwsgi/apps-available/vpn-proxy.ini << EOF
[uwsgi]

chdir = $DIR/vpn-proxy
module = project.wsgi

http-socket = $SOCKET
processes = 4

master = true
vacuum = true

uid = root
gid = root
EOF
cat /etc/uwsgi/apps-available/vpn-proxy.ini
ln -sf /etc/uwsgi/apps-available/vpn-proxy.ini /etc/uwsgi/apps-enabled/
service uwsgi status vpn-proxy || service uwsgi start vpn-proxy

echo 1 > /proc/sys/net/ipv4/ip_forward
