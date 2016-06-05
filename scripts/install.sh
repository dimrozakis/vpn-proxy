#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"

install() {
    if [ -z "$1" ]; then
        return 1
    fi
    local pkg=$1
    if [ -z "$2" ]; then
        local cmd=$1
    else
        local cmd=$2
    fi
    if ! command -v $cmd > /dev/null; then
        echo "Installing $pkg ..."
        if ! apt-get install -y $pkg; then
            apt-get update && apt-get install -y $pkg
        fi
    else
        echo "$pkg already installed."
    fi
}

install openvpn
install python
install python-pip pip

pip install -U django netaddr ipython

$DIR/vpn-proxy/manage.py migrate

echo 'from project.createsuperuser import main; main()' | \
    $DIR/vpn-proxy/manage.py shell --plain

mkdir -p $DIR/tmp

