# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

TOPOLOGY = <<EOF
      NETWORK TOPOLOGY (RAW)               NETWORK TOPOLOGY (VPN)
      ======================               ======================

             --------                             --------
             |SERVER|                             |SERVER|
             --------                             --------
          192.168.75.100               192.168.88.1 |  | 192.168.89.1
                 |                                  |  |
       __________|_________                 ________|  |________
       |        WAN       |                 |       VPN's      |
       |                  |                 |                  |
192.168.75.101     192.168.75.102     192.168.88.2        192.168.89.2
   --------            --------         --------            --------
   |PROXY1|            |PROXY2|         |PROXY1|            |PROXY2|
   --------            --------         --------            --------
  10.75.75.10        10.75.75.10       10.75.75.10        10.75.75.10
       |                  |                 |                  |
       | Private networks |                 | Private networks |
       |  with conflicts  |                 |  with conflicts  |
       |                  |                 |                  |
  10.75.75.75        10.75.75.75       10.75.75.75        10.75.75.75
   ---------          ---------         ---------          ---------
   |TARGET1|          |TARGET2|         |TARGET1|          |TARGET2|
   ---------          ---------         ---------          ---------
EOF

OPENVPN_KEY = <<EOF
#
# 2048 bit OpenVPN static key
#
-----BEGIN OpenVPN Static key V1-----
d2eb15013dc16a422de7e6bd39080657
07f5d455fa4ee0379925ddf02c5780a5
1eecc16c00e1ed7468f1c8c1d05c875e
38f2a68cb6e6d84e6915418b23999d80
dd9b1650bfdf6e782a11a74ffddbae8e
dffc83214d3db10711ae9a1b91f318bb
531abe49d2376e1ffd58673a38c9312c
c4d7ecf48d96b1bd5009e5aaff7d2e7e
d80f1418f525d48845281972fcb8ea65
53e6d8f9239df0b3cc56233ab1bc4f37
36092d5cfa8dc0a911c8dee260f7b7c6
c659068ccfc5359ac5f68260e03780e0
22948086e875c9739df6734da4d74ea7
1bea497007acd76761cc8253cb92359a
6685bbdfffd692df916b70d0a3da5b86
717610977bea9f2056e96d74b865967a
-----END OpenVPN Static key V1-----
EOF

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # Use ubuntu for all vm's. This would also work with debian/jessie64.
  config.vm.box = "ubuntu/trusty64"

  # Create a `server` vm, connected to 2 proxies.
  config.vm.define "server", primary: true do |server|
    server.vm.hostname = "server"
    server.vm.network "private_network", ip: "192.168.75.100"
    server.vm.post_up_message = TOPOLOGY

    # Set up openvpn server
    server.vm.provision "shell",
      inline: "apt-get update && apt-get install -y openvpn"
    server.vm.provision "shell",
      inline: "echo \"#{OPENVPN_KEY}\" > /etc/openvpn/static.key"
    (1..2).each do |i|
      network = "192.168.#{87+i}"
      # Create one point to point VPN for each `proxy`.
      conf = "/etc/openvpn/tun#{i}.conf"
      server.vm.provision "shell",
        inline: "echo \"dev tun#{i}\" > #{conf} && " \
                "echo \"port #{1194+i}\" >> #{conf} && " \
                "echo \"ifconfig #{network}.1 #{network}.2\" >> #{conf} && " \
                "echo \"secret /etc/openvpn/static.key\" >> #{conf} && " \
                "/etc/init.d/openvpn start"
      # Configure secondary routing tables for each `proxy`.
      server.vm.provision "shell",
        inline: "echo \"#{i}\trt_tun#{i}\" >> /etc/iproute2/rt_tables"
      server.vm.provision "shell",
        run: "always",
        inline: "ip rule add from #{network}.1 table rt_tun#{i} && " \
                "ip route add default dev tun#{i} table rt_tun#{i}"
    end
  end

  # Create two `proxy` vm's connected to `server` with each proxy also
  # connected via a private network (same address space) to a `target` server.
  (1..2).each do |i|
    config.vm.define "proxy#{i}" do |proxy|
      proxy.vm.hostname = "proxy#{i}"
      proxy.vm.network "private_network", ip: "192.168.75.#{i+100}"
      proxy.vm.network "private_network", ip: "10.75.75.10",
        virtualbox__intnet: "int#{i}"

      # Connect each `proxy` to the `server` with a point to point VPN.
      proxy.vm.provision "shell",
        inline: "apt-get update && apt-get install -y openvpn"
      proxy.vm.provision "shell",
        inline: "echo \"#{OPENVPN_KEY}\" > /etc/openvpn/static.key"
      conf = "/etc/openvpn/tun#{i}.conf"
      network = "192.168.#{87+i}"
      proxy.vm.provision "shell",
        inline: "echo \"remote 192.168.75.100\" > #{conf} && " \
                "echo \"dev tun#{i}\" >> #{conf} && " \
                "echo \"port #{1194+i}\" >> #{conf} && " \
                "echo \"ifconfig #{network}.2 #{network}.1\" >> #{conf} && " \
                "echo \"secret /etc/openvpn/static.key\" >> #{conf} && " \
                "/etc/init.d/openvpn start"

      # Enable IP forwarding and set up NAT rule.
      proxy.vm.provision "shell",
        run: "always",
        inline: "echo 1 > /proc/sys/net/ipv4/ip_forward && " \
                "iptables -t nat -A POSTROUTING -o eth2 -j MASQUERADE"
    end
  end

  # Create two `target` vm's with the same IP on different networks with the
  # same address space, each connected to its corresponding `proxy` vm.
  (1..2).each do |i|
    config.vm.define "target#{i}" do |target|
      target.vm.hostname = "target#{i}"
      target.vm.network "private_network", ip: "10.75.75.75",
        virtualbox__intnet: "int#{i}"
    end
  end

  # Fix a silly `no tty` error message in ubuntu images
  config.vm.provision "shell",
    privileged: false,
    inline: "sudo sed -i '/tty/!s/mesg n/tty -s \\&\\& mesg n/' /root/.profile"

  # Start a simple HTTP server that responds with the vm's hostname on all vm's
  config.vm.provision "shell",
    run: "always",
    inline: "mkdir -p /tmp/http && cd /tmp/http && " \
            "ln -sf /etc/hostname index.html ; " \
            "nohup python -m SimpleHTTPServer 80 >/dev/null 2>&1 </dev/null &"

end
