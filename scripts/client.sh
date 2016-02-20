#!/bin/bash

TUN="__TUN__"
REMOTE_IP="__REMOTE_IP__"
SERVER_IP="__SERVER_IP__"
CLIENT_IP="__CLIENT_IP__"
PORT="__PORT__"
KEY="__KEY__"

if ! which openvpn > /dev/null; then
    if ! which apt-get > /dev/null; then
        echo "Couldn't find apt-get to install OpenVPN."
        exit 1
    fi
    apt-get update && apt-get install -y openvpn
fi

echo "$KEY" >> /etc/openvpn/${TUN}.key
cat > /etc/openvpn/${TUN}.conf << EOF
remote $REMOTE_IP
dev $TUN
port $PORT
ifconfig $CLIENT_IP $SERVER_IP
secret /etc/openvpn/${TUN}.key
EOF
service openvpn start $TUN

echo 1 > /proc/sys/net/ipv4/ip_forward

ifaces=`ip link show | grep '^[0-9]*:' | awk '{print $2}' | sed 's/:$//'`
eth_ifaces=`echo "$ifaces" | grep ^eth`
for iface in $eth_ifaces; do
    iptables -t nat -A POSTROUTING -o $iface -j MASQUERADE
done
