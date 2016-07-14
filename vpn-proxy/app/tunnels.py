from django.conf import settings

import os
import re
import logging
import tempfile
import subprocess


REMOTE_IP = settings.VPN_SERVER_REMOTE_ADDRESS

log = logging.getLogger(__name__)


def run(cmd, shell=False, verbosity=1):
    """Run given command and return output"""
    _cmd = ' '.join(cmd) if not isinstance(cmd, basestring) else cmd
    if verbosity > 1:
        log.info("Running command '%s'.", _cmd)
    elif verbosity > 0:
        log.debug("Running command '%s'.", _cmd)
    try:
        output = subprocess.check_output(cmd, shell=shell,
                                         stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        log.error("Command '%s' exited with %d. Output was:\n%s",
                  _cmd, exc.returncode, exc.output)
        raise
    except OSError as exc:
        log.error("Command '%s' failed with OSError:%s", _cmd, exc)
        raise
    if verbosity > 1:
        log.info("Command '%s' output: %s", _cmd, output)
    elif verbosity > 0:
        log.debug("Command '%s' output: %s", _cmd, output)
    return output


def write_file(path, data, name='file'):
    """Write file idempotently, return True if changed"""
    if os.path.exists(path):
        with open(path) as fobj:
            data2 = fobj.read()
        if data != data2:
            log.warning("%s %s contents don't match, overwriting.",
                        name.capitalize(), path)
            with open(path, 'wb') as fobj:
                fobj.write(data)
        else:
            log.debug("%s %s is up to date.", name.capitalize(), path)
            return False
    else:
        log.info("Writing %s to %s.", name, path)
        with open(path, 'wb') as fobj:
            fobj.write(data)
    return True


def remove_file(path, name='file'):
    """Remove file idempotently, return True if changed"""
    if os.path.exists(path):
        log.info("Removing %s %s.", name, path)
        os.unlink(path)
        return True
    log.debug("%s %s already removed.", name.capitalize(), path)
    return False


def gen_key():
    """Generate and return an OpenVPN static key"""
    path = tempfile.mkstemp()[1]
    run(['/usr/sbin/openvpn', '--genkey', '--secret', path])
    with open(path) as fobj:
        key = fobj.read()
    os.unlink(path)
    return key


def start_openvpn(iface, force=True):
    """Start OpenVPN for given iface if not running, return True if changed

    Use `force` to restart anyways
    """
    try:
        run(['systemctl', 'status', 'openvpn@%s' % iface])
        if force:
            log.info("Restarting OpenVPN server for %s.", iface)
            run(['systemctl', 'restart', 'openvpn@%s' % iface])
        else:
            log.debug("OpenVPN server for %s already running.", iface)
            return False
    except subprocess.CalledProcessError:
        log.info("OpenVPN server for %s not running, starting.", iface)
        run(['systemctl', 'start', 'openvpn@%s' % iface])
    return True


def stop_openvpn(iface):
    """Stop OpenVPN for given iface if running, return True if changed"""
    try:
        run(['systemctl', 'status', 'openvpn@%s' % iface])
        log.info("OpenVPN server for %s is running, stopping.", iface)
        run(['systemctl', 'stop', 'openvpn@%s' % iface])
    except subprocess.CalledProcessError:
        log.debug("OpenVPN server for %s already stopped.", iface)
        return False
    return True


def add_rtable(index, rtable):
    """Add custom rtable with given index, return True if changed"""
    regex = re.compile(r'^(\d+)\s*([^\s]+)\s*$')
    with open('/etc/iproute2/rt_tables', 'r') as fobj:
        lines, conflicts = [], []
        for line in fobj.readlines():
            match = regex.match(line)
            if match:
                _index, _rtable = match.groups()
                if _index == str(index) or _rtable == rtable:
                    conflicts.append((_index, _rtable))
                    continue
            lines.append(line)
    if len(conflicts) == 1 and conflicts[0] == (str(index), rtable):
        log.debug("Routing table %s already created.", rtable)
        return False
    if conflicts:
        log.warning("Creating rtable %s, removing conflicting lines: %s",
                    rtable, conflicts)
    else:
        log.info("Creating rtable %s.", rtable)
    lines.append('%s\t%s\n' % (index, rtable))
    with open('/etc/iproute2/rt_tables', 'w') as fobj:
        fobj.writelines(lines)
    return True


def del_rtable(index, rtable):
    """Delete custom rtable with given index, return True if changed"""
    with open('/etc/iproute2/rt_tables', 'r') as fobj:
        _lines = fobj.readlines()
    regex = re.compile(r'^(%s)\s*(%s)\s*$' % (index, rtable))
    lines = [line for line in _lines if not regex.match(line)]
    if len(lines) == len(_lines):
        log.debug("Routing table %s already removed.", rtable)
        return False
    log.info("Removing routing table %s.", rtable)
    with open('/etc/iproute2/rt_tables', 'w') as fobj:
        fobj.writelines(lines)
    return True


def check_ip_rule(server, rtable):
    """Check if IP rule for src address `server` to `rtable` exists"""
    line = 'from %s lookup %s' % (server, rtable)
    return line in run(['ip', 'rule', 'list'], verbosity=0)


def add_ip_rule(server, rtable):
    if check_ip_rule(server, rtable):
        log.debug("IP rule for %s already configured.", rtable)
        return False
    log.info("Adding IP rule for %s.", rtable)
    run(['ip', 'rule', 'add', 'from', server, 'table', rtable], verbosity=2)
    return True


def del_ip_rule(server, rtable):
    if not check_ip_rule(server, rtable):
        log.debug("IP rule for %s already removed.", rtable)
        return False
    log.info("Removing IP rule for %s.", rtable)
    run(['ip', 'rule', 'del', 'from', server, 'table', rtable], verbosity=2)
    return True


def check_ip_route(iface, rtable):
    line = 'default dev %s' % iface
    try:
        return line in run(['ip', 'route', 'list', 'table', rtable],
                           verbosity=0)
    except subprocess.CalledProcessError:
        return False


def add_ip_route(iface, rtable):
    if check_ip_route(iface, rtable):
        log.debug("IP route for %s already configured.", rtable)
        return False
    log.info("Adding IP route for %s.", rtable)
    run(['ip', 'route', 'add', 'default',
         'dev', iface, 'table', rtable],
        verbosity=2)
    return True


def del_ip_route(iface, rtable):
    if not check_ip_route(iface, rtable):
        log.debug("IP route for %s already removed.", rtable)
        return False
    log.info("Removing IP route for %s.", rtable)
    run(['ip', 'route', 'del', 'default',
         'dev', iface, 'table', rtable],
        verbosity=2)
    return True


def check_rp_filter(path, iface):
    """Set loose reverse path filter in order to allow
    incoming NATed packets on vpn-proxy tuns"""
    with open(path, 'r') as rp:
        if '2' not in rp.read():
            with open(path, 'wb') as rp:
                rp.write('2')
                log.info("Enabling loose reverse path filtering for %s.",
                         iface)
                return True
        else:
            log.debug("Loose reverse path filter already enabled for %s.",
                      iface)
            return False


def get_conf(tunnel):
    return '\n'.join(['dev %s' % tunnel.name,
                      'dev-type tun',
                      'port %s' % tunnel.port,
                      'ifconfig %s %s' % (tunnel.server, tunnel.client),
                      'secret %s' % tunnel.key_path])


def get_client_conf(tunnel):
    return '\n'.join(['remote %s' % REMOTE_IP,
                      'dev %s' % tunnel.name,
                      'dev-type tun',
                      'port %s' % tunnel.port,
                      'ifconfig %s %s' % (tunnel.client, tunnel.server),
                      'secret %s' % tunnel.key_path])


def get_client_script(tunnel):
    return """#!/bin/bash

set -ex

install_pkg() {
    echo "Searching for apt-get, yum, or zypper.."
    if which apt-get > /dev/null; then
        apt-get update && apt-get install -y $1
    elif which yum > /dev/null; then
        yum update && yum install -y $1
    elif which zypper > /dev/null; then
        zypper refresh && zypper install $1
    else
        echo "Could not find a package management tool"
        exit 1
    fi

}

if ! which openvpn > /dev/null; then
    install_pkg openvpn
fi

cat > %(key_path)s << EOF
%(key)s
EOF

cat > %(conf_path)s << EOF
%(conf)s
EOF

if which systemctl > /dev/null; then
    systemctl restart openvpn@%(name)s
else
    service openvpn restart %(name)s
fi

echo 1 > /proc/sys/net/ipv4/ip_forward

ifaces=`ip link show | grep '^[0-9]*:' | awk '{print $2}' | sed 's/:$//'`
eth_ifaces=`echo "$ifaces" | grep ^eth`
for iface in $eth_ifaces; do
    iptables -t nat -A POSTROUTING -o $iface -j MASQUERADE
done
""" % {'key_path': tunnel.key_path, 'conf_path': tunnel.conf_path,
       'key': tunnel.key, 'conf': get_client_conf(tunnel), 'name': tunnel.name}


def check_iptables(forwarding, job='-C', rule=''):
    """mangle incoming packets based on local port, mangle table is traversed
    before nat in every chain
    DNAT incoming packets in order to force forwarding --> private host (IP,
    PORT)
    MASQUERADE packets routed via the virtual interface"""
    mangle_rule = ['iptables', '-t', 'mangle', job, 'PREROUTING',
                   '-p', 'tcp', '-s', str(forwarding.src_addr),
                   '--destination-port', str(forwarding.loc_port),
                   '-j', 'MARK', '--set-mark', str(forwarding.tunnel.id)]

    nat_rule = ['iptables', '-t', 'nat', job, 'PREROUTING',
                '-p', 'tcp', '-s', str(forwarding.src_addr),
                '--destination-port', str(forwarding.loc_port),
                '-j', 'DNAT', '--to-destination', str(forwarding.destination)]

    mask_rule = ['iptables', '-t', 'nat', job, 'POSTROUTING',
                 '-p', 'tcp', '-o', str(forwarding.tunnel.name),
                 '-s', str(forwarding.src_addr),
                 '-d', str(forwarding.dst_addr),
                 '--destination-port', str(forwarding.dst_port),
                 '-j', 'MASQUERADE']
    rules = {'mangle': mangle_rule, 'nat': nat_rule, 'mask': mask_rule}
    if job == '-C' and rule == '':
        exitcodes = {}
        for name, cmd in rules.iteritems():
            try:
                run(cmd, verbosity=0)
                exitcodes[name] = 0
            except subprocess.CalledProcessError as err:
                exitcodes[name] = err.returncode
        return exitcodes
    else:
        if rule == 'mangle':
            run(mangle_rule)
        elif rule == 'nat':
            run(nat_rule)
        elif rule == 'mask':
            run(mask_rule)


def add_iptables(forwarding):
    exitcodes = check_iptables(forwarding)
    for rule, exitcode in exitcodes.iteritems():
        if exitcode == 0:
            log.debug('IPtables %s rule already in place for local port '
                      '%s.' % (rule, forwarding.loc_port))
        else:
            check_iptables(forwarding, '-A', rule)
            log.info('Appending %s rule for local port %s' %
                     (rule, forwarding.loc_port))


def del_iptables(forwarding):
    exitcodes = check_iptables(forwarding)
    for rule, exitcode in exitcodes.iteritems():
        if exitcode == 0:
            check_iptables(forwarding, '-D', rule)
            log.info('Removing IPtables %s rule for local port %s' %
                     (rule, forwarding.loc_port))
        else:
            log.debug('IPtables %s for local port %s already deleted.' %
                      (rule, forwarding.loc_port))


def check_fwmark(mark, table):
    line = 'from all fwmark %s lookup %s' % (hex(mark), table)
    if line in run(['ip', 'rule', 'show'], verbosity=0):
        return True
    return False


def add_fwmark(forwarding):
    """point marked packets to the corresponding routing table
    as created during `openvpn start`"""
    ip_rule = ['ip', 'rule', 'add', 'fwmark', str(hex(forwarding.tunnel.id)),
               'table', str(forwarding.tunnel.rtable)]
    if check_fwmark(forwarding.tunnel.id, forwarding.tunnel.rtable):
        log.debug('IP rule for mark %s already exists.', forwarding.tunnel.id)
    else:
        run(ip_rule)
        log.info('Inserting IP rule for fwmark %s pointing to routing table'
                 ' %s' % (forwarding.tunnel.id, forwarding.tunnel.rtable))


def del_fwmark(forwarding):
    ip_rule = ['ip', 'rule', 'delete',
               'fwmark', str(hex(forwarding.tunnel.id)),
               'table', str(forwarding.tunnel.rtable)]
    if check_fwmark(forwarding.tunnel.id, forwarding.tunnel.rtable):
        run(ip_rule)
        log.info('Removing IP rule for fwmark %s pointing to routing table'
                 ' %s' % (forwarding.tunnel.id, forwarding.tunnel.rtable))
    else:
        log.debug('IP rule for mark % already removed.', forwarding.tunnel.id)


def start_tunnel(tunnel):
    write_file(tunnel.key_path, tunnel.key, 'key file')
    write_file(tunnel.conf_path, get_conf(tunnel), 'conf file')
    start_openvpn(tunnel.name)
    add_rtable(tunnel.id, tunnel.rtable)
    add_ip_rule(tunnel.server, tunnel.rtable)
    add_ip_route(tunnel.name, tunnel.rtable)
    check_rp_filter(tunnel.rp_filter, tunnel.name)


def stop_tunnel(tunnel):
    del_ip_route(tunnel.name, tunnel.rtable)
    del_ip_rule(tunnel.server, tunnel.rtable)
    del_rtable(tunnel.id, tunnel.rtable)
    stop_openvpn(tunnel.name)
    remove_file(tunnel.conf_path, 'conf file')
    remove_file(tunnel.key_path, 'key file')
