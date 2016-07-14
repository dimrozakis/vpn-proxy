#!/usr/bin/env bash

SERVER="192.168.69.100:8080"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"

SSH="ssh -F ssh-config"

set -ex

cd $DIR
mkdir -p tmp/

vagrant ssh-config > ssh-config || true

for i in {1..2}; do
    echo "Attempting to create tunnel $i"
    $SSH peer curl -fsS -X POST -d cidrs='10.75.75.0/24' $SERVER/
    $SSH peer curl -fsS $SERVER/$i/client_script/ > tmp/proxy$i.sh
    $SSH peer curl -fsS $SERVER/$i/forwardings/10.75.75.75/80/ > tmp/target${i}_port.txt
    $SSH proxy$i sudo bash < tmp/proxy$i.sh
done
