# Cronjob directory for vpn-proxy

Executables contained in this directory are used to create cronjobs.

## IPtables Retention

In order to minimize the overhead of parsing large IPtables chains, we are
applying an IPtables retention policy. The `iptables.sh` appends a daily
cronjob under /etc/cron.daily/ in order to take care of disabling IPtables
rules, which have not been updated the last 24h.
