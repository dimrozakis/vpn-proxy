#!/bin/bash

set -e

NETWORK="172.17.17"
VERBOSITY=0

br() { echo >&2; }
debug() { if [ "$VERBOSITY" -gt 0 ]; then echo "DEBUG: $@" >&2; fi }
debug_cmd() { debug "Will run command: $@"; }
info() { echo "INFO: $@" >&2; }
warning() { echo "WARNING: $@" >&2; }
error() { echo "ERROR: $@" >&2; }

check_requirements() {
    # Check if iproute2 and OpenVPN are installed.
    if ! which openvpn > /dev/null; then
        if [ -z "$INSTALL" ]; then
            error "OpenVPN not installed and -i flag wasn't set."
            return 1
        fi
        warning "OpenVPN wan't found, will try to install..."
        if ! which apt-get > /dev/null; then
            error "Couldn't find apt-get to install OpenVPN."
            return 1
        fi
        debug_cmd "apt-get update && apt-get install -y openvpn"
        apt-get update && apt-get install -y openvpn
        br
        CHANGED=1
    fi
    if ! which ip > /dev/null; then
        error "Couldn't find iproute2."
        return 1
    fi
    debug "Found openvpn and iproute2."
}

find_tunnels() {
    # Find all tunnels that have a conf file.
    find /etc/openvpn/ -type f -name 'tun[0-9]*.conf' | \
        grep -o '[0-9]*' | sort -n
}

find_free_tun_num() {
    # Find first free tunnel number available (above 0).
    find_tunnels |
        awk '$1!=p+1{for(i=p+1;i<$1;i++)print i}{p=$1}END{print p+1}' | \
        head -n 1
}

set_globals() {
    # Set global variables with tunnel attributes for tunnel number $1
    # This needs to be called before any other function that follows.
    if [ -z "$1" ]; then
        error "check_tun_num: No number specified."
        return 1
    fi
    if [ "$1" -gt 127 ]; then
        error "Maximum number of tunnels (127) exceeded."
        return 1
    fi
    NUM=$1
    TUN=tun$NUM
    KEY=/etc/openvpn/${TUN}.key
    CONFIG=/etc/openvpn/${TUN}.conf
    SERVER_IP=${NETWORK}.$((2*$NUM-1))
    CLIENT_IP=${NETWORK}.$((2*$NUM))
    PORT=$((1194+$NUM))
    RTABLE=rt_$TUN
}

echo_globals() {
    br
    debug "OpenVPN settings"
    debug "================"
    debug "Device:          $TUN"
    debug "Port:            $PORT"
    debug "Server:          $SERVER_IP"
    debug "Client:          $CLIENT_IP"
    debug "Key:             $KEY"
    debug "Config:          $CONFIG"
    debug "Routing table:   $RTABLE"
    br
}

add_key() {
    # Generate OpenVPN static key and store to $KEY (do nothing if it exists)
    if [ ! -f "$KEY" ]; then
        info "Generating OpenVPN static key and saving to $KEY ..."
        debug_cmd "openvpn --genkey --secret $KEY"
        openvpn --genkey --secret $KEY
        CHANGED=1
    else
        debug "OpenVPN key $KEY already created."
    fi
}

del_key() {
    # Remove key $KEY if it exists
    if [ -f $KEY ]; then
        info "Removing key $KEY"
        rm $KEY
        CHANGED=1
    else
        debug "Key $KEY already removed"
    fi
}

add_conf() {
    cat > /tmp/${TUN}.conf << EOF
dev $TUN
port $PORT
ifconfig $SERVER_IP $CLIENT_IP
secret $KEY
EOF
    if [ -f $CONFIG ]; then
        if diff /tmp/${TUN}.conf $CONFIG > /dev/null; then
            debug "File $CONFIG already exists and hasn't been modified."
            return
        fi
        warning "File $CONFIG already exists and has been modified:"
        diff /tmp/${TUN}.conf $CONFIG >&2 || true
        br
        if [ -z "$FORCE" ]; then
            warning "Use -f (force) to overwrite."
            return 1
        fi
        info "Overwriting OpenVPN config file..."
    else
        info "Generating OpenVPN config file..."
    fi
    debug_cmd "cp /tmp/${TUN}.conf $CONFIG"
    cp /tmp/${TUN}.conf $CONFIG
    CHANGED=1
}

del_conf() {
    # Remove configuration file $CONFIG if it exists.
    if [ -f $CONFIG ]; then
        info "Removing config file $CONFIG"
        debug_cmd "rm $CONFIG"
        rm $CONFIG
        CHANGED=1
    else
        debug "Config file $CONFIG already removed."
    fi
}

start_openvpn() {
    # Start OpenVPN server for tunnel $TUN
    if service openvpn status $TUN > /dev/null; then
        if [ "$CHANGED" ]; then
            info "Restarting OpenVPN server due to changes in configuration."
            debug_cmd "service openvpn restart $TUN"
            service openvpn restart $TUN
        else
            debug "OpenVPN server for $TUN is already running."
        fi
    else
        info "OpenVPN server for $TUN not running, starting..."
        debug_cmd "service openvpn start $TUN"
        service openvpn start $TUN
        CHANGED=1
    fi
}

stop_openvpn() {
    # Stop openvpn for tunnel $TUN
    if service openvpn status $TUN > /dev/null; then
        info "Stoping OpenVPN server for $TUN"
        debug_cmd "service openvpn stop $TUN"
        service openvpn stop $TUN
        CHANGED=1
    else
        debug "OpenVPN server for $TUN already stopped."
    fi
}

add_rtable() {
    # Add routing table with index $NUM and name $RTABLE
    local line="$NUM $RTABLE"
    local conflicts=$(
        cat /etc/iproute2/rt_tables | grep -v ^# | \
        grep -e "^$NUM\s\s*" -e "\s*$RTABLE\s*$" || true
    )
    if [ -n "$conflicts" ]; then
        if [ "$conflicts" == "$line" ]; then
            debug "Routing table $RTABLE already properly created."
            return
        fi
        warning "Routing table entry confict. Found:"
        warning "$conflicts"
        warning "Expected: \"$line\""
        if [ -z "$FORCE" ]; then
            warning "Use -f (force) to overwrite."
            return 1
        fi
        info "Overwriting routing tables configuration..."
        debug_cmd "sed -i "/^$NUM\s\s*.*$/d" /etc/iproute2/rt_tables"
        sed -i "/^$NUM\s\s*.*$/d" /etc/iproute2/rt_tables
        debug_cmd "sed -i "/^.*\s*$RTABLE\s*$/d" /etc/iproute2/rt_tables"
        sed -i "/^.*\s*$RTABLE\s*$/d" /etc/iproute2/rt_tables
    else
        info "Creating routing table $RTABLE"
    fi
    debug_cmd "echo $line >> /etc/iproute2/rt_tables"
    echo $line >> /etc/iproute2/rt_tables
    sed -i '/^\s*$/d' /etc/iproute2/rt_tables
    CHANGED=1
}

del_rtable() {
    local line="$NUM $RTABLE"
    if grep "^$line" /etc/iproute2/rt_tables > /dev/null; then
        info "Removing routing table $RTABLE"
        debug_cmd "sed -i \"/^${line}.*$/d\" /etc/iproute2/rt_tables"
        sed -i "/^${line}.*$/d" /etc/iproute2/rt_tables
        sed -i '/^\s*$/d' /etc/iproute2/rt_tables
        CHANGED=1
    else
        debug "Routing table $RTABLE already removed."
    fi
}

add_ip_rule() {
    # Add ip rule from ip $SERVER_IP to routing table $RTABLE
    if ! ip rule list | grep "from $SERVER_IP lookup $RTABLE" > /dev/null; then
        info "Adding ip rule from $SERVER_IP table $RTABLE"
        debug_cmd "ip rule add from $SERVER_IP table $RTABLE"
        ip rule add from $SERVER_IP table $RTABLE
        CHANGED=1
    else
        debug "Ip rule from $SERVER_IP table $RTABLE already present."
    fi
}

del_ip_rule() {
    if ip rule list | grep "from $SERVER_IP lookup $RTABLE" > /dev/null; then
        info "Removing ip rule from $SERVER_IP table $RTABLE"
        debug_cmd "ip rule del from $SERVER_IP table $RTABLE"
        ip rule del from $SERVER_IP table $RTABLE
        CHANGED=1
    else
        debug "Ip rule from $SERVER_IP table $RTABLE already removed."
    fi
}

add_ip_route() {
    # Add default gateway for device $TUN in routing table $RTABLE
    if ! ip route list table $RTABLE | \
            grep "^default dev $TUN" > /dev/null; then
        info "Adding ip route default dev $TUN table $RTABLE"
        debug_cmd "ip route add default dev $TUN table $RTABLE"
        ip route add default dev $TUN table $RTABLE
        CHANGED=1
    else
        debug "ip route default dev $TUN table $RTABLE already present."
    fi
}

del_ip_route() {
    # Remove default gateway for device $TUN in routing table $RTABLE
    if ip route list table $RTABLE | grep "^default dev $TUN" > /dev/null; then
        info "Removing ip route default dev $TUN table $RTABLE"
        debug_cmd "ip route del default dev $TUN table $RTABLE"
        ip route del default dev $TUN table $RTABLE
        CHANGED=1
    else
        debug "Ip route default dev $TUN table $RTABLE already removed."
    fi
}

start() {
    # Start tunnel number $1. If not specified, will autoselect tunnel.
    check_requirements
    local num=$1
    if [ -z "$num" ]; then
        num=`find_free_tun_num`
        info "Found lowest free tunnel number available (above 0): $num"
    fi
    set_globals $num
    echo_globals
    add_key
    add_conf
    start_openvpn
    add_rtable
    add_ip_rule
    add_ip_route
}

stop() {
    # Stop tunnel number $1.
    check_requirements
    set_globals $1
    echo_globals
    stop_openvpn
    if [ "$RM" ]; then
        del_conf
        del_key
    fi
    del_ip_route
    del_ip_rule
    del_rtable
}

get_client_conf() {
    # Print in stdout a short shell script to set up client for tunnel $1
    check_requirements
    set_globals $1
    if [ -z "$REMOTE_IP" ]; then
        info "No REMOTE_IP specified with the -r flag, will try to discover."
        debug_cmd "curl -s api.ipify.org"
        REMOTE_IP=`curl -s api.ipify.org`
        info "Remote IP will be set to $REMOTE_IP"
    fi
    br
    local key=`cat $KEY | tr '\n' '~'|sed 's/~/\\\\n/g'`
    local dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    cat $dir/client.sh | \
        sed "s/__TUN__/$TUN/" | \
        sed "s/__REMOTE_IP__/$REMOTE_IP/" | \
        sed "s/__SERVER_IP__/$SERVER_IP/" | \
        sed "s/__CLIENT_IP__/$CLIENT_IP/" | \
        sed "s/__PORT__/$PORT/" | \
        sed "s/__KEY__/${key}/"
}


##### CLI argument parsing ####

HELP="Usage: $0 {start,stop,list,client-conf,help}"

HELP_START="Usage: $0 start [options] [TUN_IFACE_NUMBER]

Start a OpenVPN point-to-point tunnel (server side) and configure appropriate
rules so that any traffic bound to the tun interface can be forwarded.

This operation is applied in an idempotent way (if TUN_IFACE_NUMBER has been
specified), so it is safe to call multiple times.

Arguments:
TUN_IFACE_NUMBER  The number of the tun interface to use. If not specified, the
                  first free number will be used. If the interface already
                  exists, it will be checked to see if anything is out of order
                  in the configuration of the interface. If there's any
                  difference, the script will fail unless -f is used which will
                  cause the configuration of the interface to be reset.

Options:
-h           Show this help message.
-i           If OpenVPN is not found, try to install it. Only works with
             apt-get.
-f           Force overwrite of existing tunel if it already exists.
-n NET_PREF  Specify a different subnet to use for point to point VPN channels.
             This must be a /24 network expressed as three dotted separated
             octes. The default value is \"$NETWORK\".
-v           Increase verbosity.
"

HELP_STOP="Usage: $0 stop [options] TUN_IFACE_NUMBER

Stop the OpenVPN tunnel with the given number and removing relevant routing
tables and rules.

This operation is applied in an idempotent way, so it is safe to call multiple
times.

Arguments:
TUN_IFACE_NUMBER  The number of the tun interface to remove.

Options:
-h           Show this help message.
-d           Stop and purge configuration files, including key.
-n NET_PREF  Specify a different subnet to use for point to point VPN channels.
             This must be a /24 network expressed as three dotted separated
             octes. The default value is \"$NETWORK\".
-v           Increase verbosity.
"

HELP_CLIENT="Usage: $0 client-conf [options] TUN_IFACE_NUMBER

Print a short shell script on stdout that can be run on the client to set up
the OpenVPN channel and ip forwarding.

Arguments:
TUN_IFACE_NUMBER  The number of the tun interface to remove.

Options:
-h           Show this help message.
-r REMOTE_IP Remote IP to use.
-n NET_PREF  Specify a different subnet to use for point to point VPN channels.
             This must be a /24 network expressed as three dotted separated
             octes. The default value is \"$NETWORK\".
-v           Increase verbosity.
"
case $1 in
    help|-h|--help)
        echo "$HELP"
        exit
        ;;
    start)
        shift
        while getopts "hifn:v" opt; do
            case $opt in
                h)
                    echo "$HELP_START"
                    exit
                    ;;
                i)
                    INSTALL=1
                    ;;
                f)
                    FORCE=1
                    ;;
                n)
                    NETWORK=$OPTARG
                    ;;
                v)
                    VERBOSITY=1
                    ;;
                \?)
                    echo "Invalid option: -$OPTARG" >&2
                    echo "$HELP_START" >&2
                    exit 1
                    ;;
            esac
        done
        NUM=${@:$OPTIND:1}
        start $NUM
        ;;
    stop)
        shift
        while getopts "hn:v" opt; do
            case $opt in
                h)
                    echo "$HELP_STOP"
                    exit
                    ;;
                d)
                    RM=1
                    ;;
                n)
                    NETWORK=$OPTARG
                    ;;
                v)
                    VERBOSITY=1
                    ;;
                \?)
                    echo "Invalid option: -$OPTARG" >&2
                    echo "$HELP_STOP" >&2
                    exit 1
                    ;;
            esac
        done
        NUM=${@:$OPTIND:1}
        stop $NUM
        ;;
    client-conf)
        shift
        while getopts "hr:n:v" opt; do
            case $opt in
                h)
                    echo "$HELP_CLIENT"
                    exit
                    ;;
                r)
                    REMOTE_IP=$OPTARG
                    ;;
                n)
                    NETWORK=$OPTARG
                    ;;
                v)
                    VERBOSITY=1
                    ;;
                \?)
                    echo "Invalid option: -$OPTARG" >&2
                    echo "$HELP_CLIENT" >&2
                    exit 1
                    ;;
            esac
        done
        NUM=${@:$OPTIND:1}
        get_client_conf $NUM
        ;;
    list)
        find_tunnels
        ;;
    *)
        if [ -z "$1" ]; then
            echo "No command specified." >&2
        else
            echo "Invalid command $1" >&2
        fi
        echo "$HELP" >&2
        exit 1
        ;;
esac
