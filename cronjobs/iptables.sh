#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"
LOG="$DIR/iptables-retention.log"

cat > /etc/cron.daily/vpn-proxy-iptables << EOF
#!/bin/sh

main () {
    echo
    echo "=========== IPtables Retention ==========="
    echo "Triggered at: `date`"
    echo "=========================================="
    echo
    cd $DIR/vpn-proxy && ./manage.py retain_iptables
}

main >> $LOG 2>&1
EOF
chmod +x /etc/cron.daily/vpn-proxy-iptables

echo "Cronjob for IPtables retention added under /etc/cron.daily/"
