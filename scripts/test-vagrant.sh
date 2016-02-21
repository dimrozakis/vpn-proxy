#!/bin/bash

assert_probe() {
    TOTAL=$(($TOTAL+1))
    local msg="$2\t\t$1\t\t$3\t\t"
    local curl_opts="-s -m 2"
    if [ "$4" ]; then
        msg="$msg$4"
        curl_opts="$curl_opts --interface $4"
    else
        msg="$msg-"
    fi
    echo -ne "$msg\t\t"

    if [ "$MODE" = "python" ]; then
        cmd="sudo python /vagrant/scripts/bind_iface.py $2 $4"
    else
        cmd="curl $curl_opts $2"
    fi
    local result=`vagrant ssh $1 -c "$cmd | tr -d '\r\n'" 2> /dev/null`
    local error=$?
    if [ "$error" -gt 0 ]; then
        echo "ERROR: Return code $error, result \"$result\"."
        return 1
    fi
    if [ "$result" != "$3" ]; then
        echo "ERROR: \"$result\"."
        return 1
    fi
    OK=$(($OK+1))
    echo "OK"
}

HEADER="When we probe\t\tfrom\t\twe see\t\tvia\t\tcheck"

test_selfprobe() {
    echo "Test that each server can probe itself on all interfaces"
    echo "--------------------------------------------------------"
    echo
    echo "### server ###"
    echo -e $HEADER
    assert_probe server 127.0.0.1 server
    assert_probe server 192.168.75.100 server
    echo
    echo "### proxy1 ###"
    echo -e $HEADER
    assert_probe proxy1 127.0.0.1 proxy1
    assert_probe proxy1 192.168.75.101 proxy1
    assert_probe proxy1 10.75.75.10 proxy1
    assert_probe proxy1 10.75.76.10 proxy1
    echo
    echo "### proxy2 ###"
    echo -e $HEADER
    assert_probe proxy2 127.0.0.1 proxy2
    assert_probe proxy2 192.168.75.102 proxy2
    assert_probe proxy2 10.75.75.10 proxy2
    assert_probe proxy2 10.75.77.10 proxy2
    echo
    echo "### target1 ###"
    echo -e $HEADER
    assert_probe target1 127.0.0.1 target1
    assert_probe target1 10.75.75.75 target1
    echo
    echo "### target2 ###"
    echo -e $HEADER
    assert_probe target2 127.0.0.1 target2
    assert_probe target2 10.75.75.75 target2
    echo
    echo "### target3 ###"
    echo -e $HEADER
    assert_probe target3 127.0.0.1 target3
    assert_probe target3 10.75.76.75 target3
    echo
    echo "### target4 ###"
    echo -e $HEADER
    assert_probe target4 127.0.0.1 target4
    assert_probe target4 10.75.77.75 target4
}

test_proxy_targets() {
    echo "Test that each proxy can probe with its targets"
    echo "-----------------------------------------------"
    echo
    echo "### proxy1 <-> target1 ###"
    echo -e $HEADER
    assert_probe proxy1 10.75.75.75 target1
    assert_probe target1 10.75.75.10 proxy1
    echo
    echo "### proxy1 <-> target3 ###"
    echo -e $HEADER
    assert_probe proxy1 10.75.76.75 target3
    assert_probe target3 10.75.76.10 proxy1
    echo
    echo "### proxy2 <-> target2 ###"
    echo -e $HEADER
    assert_probe proxy2 10.75.75.75 target2
    assert_probe target2 10.75.75.10 proxy2
    echo
    echo "### proxy2 <-> target4 ###"
    echo -e $HEADER
    assert_probe proxy2 10.75.77.75 target4
    assert_probe target4 10.75.77.10 proxy2
}

test_server_proxies() {
    echo "Test that the server can probe with the proxies"
    echo "-----------------------------------------------"
    echo
    echo "### server <-> proxy1 ###"
    echo -e $HEADER
    assert_probe server 192.168.75.101 proxy1
    assert_probe proxy1 192.168.75.100 server
    echo
    echo "### server <-> proxy2 ###"
    echo -e $HEADER
    assert_probe server 192.168.75.102 proxy2
    assert_probe proxy2 192.168.75.100 server
}

test_server_targets() {
    echo "Test that the server can probe the targets through the proxies"
    echo "--------------------------------------------------------------"
    echo
    echo -e $HEADER
    assert_probe server 10.75.75.75 target1 tun1
    assert_probe server 10.75.75.75 target2 tun2
    assert_probe server 10.75.76.75 target3 tun1
    assert_probe server 10.75.77.75 target4 tun2
}

test() {
    echo "Testing using $MODE"
    echo "==================="
    echo
    echo
    test_selfprobe
    echo
    echo
    test_proxy_targets
    echo
    echo
    test_server_proxies
    echo
    echo
    test_server_targets
    echo
    echo
    echo "Failed: $(($TOTAL-$OK))/$TOTAL"
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Usage: $0 [-h|--help] [curl|python]"
    exit
fi
MODE=$1
if [ -z "$MODE" ]; then MODE="curl"; fi
test
