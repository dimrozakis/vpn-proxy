#!/bin/bash

assert_probe() {
    local msg="$2\t\t   $1\t   $3\t   "
    local curl_opts="-s -m 2"
    if [ "$4" ]; then
        msg="$msg$4"
        curl_opts="$curl_opts --interface $4"
    else
        msg="$msg-   "
    fi
    echo -ne "$msg\t   "

    result=`vagrant ssh $1 -c "curl $curl_opts $2 | tr -d '\r\n'" 2> /dev/null`
    error=$?
    if [ "$error" -gt 0 ]; then
        echo "ERROR: Return code $error, result \"$result\"."
        return 1
    fi
    if [ "$result" != "$3" ]; then
        echo "ERROR: \"$result\"."
        return 1
    fi
    echo "OK"
}

echo -e "Test that when we probe\t   from\t\t   we see\t   via\t   result"

# check that each server can probe itself on all interfaces
assert_probe server 127.0.0.1 server
assert_probe server 192.168.75.100 server
assert_probe proxy1 127.0.0.1 proxy1
assert_probe proxy1 192.168.75.101 proxy1
assert_probe proxy1 10.75.75.10 proxy1
assert_probe proxy2 127.0.0.1 proxy2
assert_probe proxy2 192.168.75.102 proxy2
assert_probe proxy2 10.75.75.10 proxy2
assert_probe target1 127.0.0.1 target1
assert_probe target1 10.75.75.75 target1
assert_probe target2 127.0.0.1 target2
assert_probe target2 10.75.75.75 target2

# check that proxies and targets can probe each other in pairs
assert_probe target1 10.75.75.10 proxy1
assert_probe proxy1 10.75.75.75 target1
assert_probe target2 10.75.75.10 proxy2
assert_probe proxy2 10.75.75.75 target2

# check that the server can be probed with each proxie
assert_probe server 192.168.75.101 proxy1
assert_probe proxy1 192.168.75.100 server
assert_probe server 192.168.75.102 proxy2
assert_probe proxy2 192.168.75.100 server

# check that the server can probe the targets
assert_probe server 10.75.75.75 target1 tun1
assert_probe server 10.75.75.75 target2 tun2
