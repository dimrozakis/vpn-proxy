#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"

OK=0
FAILED=0
SKIPPED=0
TOTAL=0

is_up() {
    [ -z "$1" ] && return 1
    local state=$(vagrant status --machine-readable $1 | \
                  grep "^[0-9]*,$1,state," | cut -d, -f4)
    if [ "$state" != "running" ]; then
        return 1
    fi
}

assert_probe() {
    TOTAL=$(($TOTAL+1))
    printf "%-24s| %-12s| " "$2" "$1"
    if [ "$4" ]; then
        printf "%-18s" "$4"
        local curl_opts="--interface $4"
    else
        printf "%-18s" "<default>"
    fi
    printf "| %-12s| " "$3"
    if ! is_up $1; then
        echo "SKIPPED: $1 not running"
        SKIPPED=$(($SKIPPED+1))
        return 2
    elif ! is_up $3; then
        echo "SKIPPED: $3 not running"
        SKIPPED=$(($SKIPPED+1))
        return 2
    fi

    if [ "$MODE" = "python" ]; then
        local cmd="sudo python /vagrant/scripts/bind_iface.py $2 $4"
    else
        local cmd="curl -s -m 2 $curl_opts $2"
    fi
    local result=`vagrant ssh $1 -c "$cmd | tr -d '\r\n'" 2> /dev/null`
    local error=$?
    if [ "$error" -gt 0 ]; then
        echo "ERROR: Return code $error, result \"$result\"."
        FAILED=$(($FAILED+1))
        return 1
    fi
    if [ "$result" != "$3" ]; then
        echo "ERROR: \"$result\"."
        FAILED=$(($FAILED+1))
        return 1
    fi
    OK=$(($OK+1))
    echo "OK"
}

get_ip() {
    local cmd="/sbin/ifconfig | grep '^$2' -A 1 | grep 'inet addr' | cut -d: -f2 | sed 's/  P-t-P$//'"
    vagrant ssh $1 -c "$cmd | tr -d '\r\n'" 2> /dev/null
}

columns() {
    printf "%-24s| %-12s| %-18s| %-12s| %s\n" \
        "When we probe" "from" "via" "we see" "check"
    printf "%0.s-" {1..79}
    echo
}

header() {
    echo $1
    if [ -z "$2" ]; then
        char="="
    else
        char=$2
    fi
    printf "%0.s$char" `seq 1 ${#1}`
    echo
    echo
}

subheader() {
    echo
    header "$1" "-"
}

test_selfprobe() {
    header "Test that each server can probe itself on all interfaces"
    subheader "server"
    columns
    local ip1=$(get_ip server mist-io-tun1)
    local ip2=$(get_ip server mist-io-tun2)
    assert_probe server 127.0.0.1 server
    assert_probe server 192.168.75.100 server
    assert_probe server 192.168.69.100 server
    assert_probe server $ip1 server
    assert_probe server $ip2 server
    echo
    subheader "proxy1"
    columns
    local ip=$(get_ip proxy1 mist-io-tun1)
    assert_probe proxy1 127.0.0.1 proxy1
    assert_probe proxy1 192.168.75.101 proxy1
    assert_probe proxy1 10.75.75.10 proxy1
    assert_probe proxy1 10.75.77.10 proxy1
    assert_probe proxy1 $ip proxy1
    echo
    subheader "proxy2"
    columns
    local ip=$(get_ip proxy2 mist-io-tun2)
    assert_probe proxy2 127.0.0.1 proxy2
    assert_probe proxy2 192.168.75.102 proxy2
    assert_probe proxy2 10.75.76.10 proxy2
    assert_probe proxy2 10.75.78.10 proxy2
    assert_probe proxy2 $ip proxy2
    echo
    subheader "target1"
    columns
    assert_probe target1 127.0.0.1 target1
    assert_probe target1 10.75.75.75 target1
    echo
    subheader "target2"
    columns
    assert_probe target2 127.0.0.1 target2
    assert_probe target2 10.75.76.75 target2
    echo
    subheader "target3"
    columns
    assert_probe target3 127.0.0.1 target3
    assert_probe target3 10.75.77.75 target3
    echo
    subheader "target4"
    columns
    assert_probe target4 127.0.0.1 target4
    assert_probe target4 10.75.78.75 target4
}

test_proxy_targets() {
    header "Test that each proxy can probe with its targets"
    subheader "proxy1 <-> target1"
    columns
    assert_probe proxy1 10.75.75.75 target1
    assert_probe target1 10.75.75.10 proxy1
    echo
    subheader "proxy1 <-> target3"
    columns
    assert_probe proxy1 10.75.77.75 target3
    assert_probe target3 10.75.77.10 proxy1
    echo
    subheader "proxy2 <-> target2"
    columns
    assert_probe proxy2 10.75.76.75 target2
    assert_probe target2 10.75.76.10 proxy2
    echo
    subheader "proxy2 <-> target4"
    columns
    assert_probe proxy2 10.75.78.75 target4
    assert_probe target4 10.75.78.10 proxy2
}

test_server_proxies() {
    header "Test that the server can probe with the proxies"
    subheader "server <-> proxy1"
    columns
    assert_probe server 192.168.75.101 proxy1
    assert_probe proxy1 192.168.75.100 server
    echo
    subheader "server <-> proxy2"
    columns
    assert_probe server 192.168.75.102 proxy2
    assert_probe proxy2 192.168.75.100 server
}

test_peer_server() {
    header "Test that the peer can probe with the server"
    columns
    assert_probe peer 192.168.69.100 server
    assert_probe server 192.168.69.69 peer
}

test_server_targets() {
    header "Test that the server can probe the targets through the proxies"
    columns
    assert_probe server 10.75.75.75 target1 mist-io-tun1
    assert_probe server 10.75.76.75 target2 mist-io-tun2
    assert_probe server 10.75.77.75 target3 mist-io-tun1
    assert_probe server 10.75.78.75 target4 mist-io-tun2
}

test_peer_targets() {
    header "Test that the peer can probe the targets through the vpn-proxy"
    columns
    local port1=$(cat $DIR/tmp/target1_port.txt)
    local port2=$(cat $DIR/tmp/target2_port.txt)
    assert_probe peer 192.168.69.100:$port1 target1
    assert_probe peer 192.168.69.100:$port2 target2
}

test_targets_server() {
    header "Test that the targets can probe the server through the proxies"
    for i in {1..2}; do
        local ip=$(get_ip server mist-io-tun$i)
        local rule="PREROUTING -t nat -p tcp --destination-port 81 -j DNAT --to-destination $ip:80"
        local cmd="sudo iptables -C $rule || sudo iptables -A $rule"
        echo "Forward all traffic coming to proxy$i:81 to server:80:"
        echo "  iptables -A $rule"
        vagrant ssh proxy$i -c "$cmd" 2> /dev/null
    done
    echo
    columns
    assert_probe target1 10.75.75.10:81 server
    assert_probe target3 10.75.77.10:81 server
    assert_probe target2 10.75.76.10:81 server
    assert_probe target4 10.75.78.10:81 server
}

test() {
    if [ "$SELF_TEST" ]; then
        test_selfprobe
        echo
        echo
    fi
    if [ "$LINK_TEST" ]; then
        test_proxy_targets
        echo
        echo
        test_server_proxies
        echo
        echo
        test_peer_server
        echo
        echo
    fi
    test_server_targets
    echo
    echo
    test_peer_targets
    echo
    echo
    test_targets_server
    echo
    echo
    echo "Summary"
    echo "======="
    echo
    echo "OK   | FAILED | SKIPPED | TOTAL"
    echo "------------------------------"
    printf "%-4s | %-6s | %-7s | %s\n" $OK $FAILED $SKIPPED $TOTAL
}

MODE="curl"
HELP="Usage: $0 [options]

Test networking in vagrant setup.

Options:
-h      Show this help message.
-s      Test that each server can locally see its webserver on all ifaces.
-l      Test that each server can probe each other directly connected server.
-p      Use python requests instead of curl to perform testing.
"

while getopts "hslp" opt; do
    case $opt in
        h)
            echo "$HELP"
            exit
            ;;
        s)
            SELF_TEST=1
            ;;
        l)
            LINK_TEST=1
            ;;
        p)
            MODE="python"
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            echo "$HELP" >&2
            exit 1
            ;;
    esac
done
test
