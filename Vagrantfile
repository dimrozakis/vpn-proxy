# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

TOPOLOGY = <<EOF
                            NETWORK TOPOLOGY
                            ================
                                                      --------
                                         172.17.0.1  |        |
                                     ________________| DOCKER |
            directly connected via  |                |        |                                    
           host OS's network stack  |                 --------
                                    |
                             192.168.2.232      
                                --------
   vpn-proxy-tun1: 172.17.17.3 |        | vpn-proxy-tun2: 172.17.17.5
                          #####| SERVER |#####
 OpenVPN point to point  #     |        |     #  OpenVPN point to point
        tunnel over WAN  #      --------      #  tunnel over WAN
                         #   192.168.75.100   #
                #########           |          ##########
               #                    |                    #
               #                    |                    #
               #   _________________|_________________   #
               #  |               (WAN)               |  #
               #  |                                   |  #
               #  |                                   |  #
   172.17.17.2 #  | 192.168.75.101     192.168.75.102 |  # 172.17.17.4
             --------                               --------
            |        | 10.75.75.10     10.75.76.10 |        |
            | PROXY1 |____                     ____| PROXY2 |
            |        |    |                   |    |        |
             --------     |  Private networks |     --------
            10.75.77.10   |  without conflict |    10.75.78.10
                 |        |     /24 CIDRs     |         |
                 |        |                   |         |
                 |        |  LAN1       LAN2  |         |
           LAN3  |        |                   |         |  LAN4
                 |        |                   |         |
                 |   10.75.75.75         10.75.76.75    |
                 |    ---------          ---------      |
                 |   |         |        |         |     |
                 |   | TARGET1 |        | TARGET2 |     |
                 |   |         |        |         |     |
                 |    ---------          ---------      |
                 |                                      |
            10.75.77.75                            10.75.78.75
             ---------                              ---------
            |         |                            |         |
            | TARGET3 |                            | TARGET4 |
            |         |                            |         |
             ---------                              ---------
EOF

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # Use ubuntu for all vm's. This would also work with debian/jessie64.
  config.vm.box = "ubuntu/trusty64"

  # Create a `server` vm, connected to 2 proxies.
  config.vm.define "server", primary: true do |server|
    server.vm.hostname = "server"
    server.vm.network "public_network", bridge: "wlan0"
    server.vm.network :forwarded_port, guest: 22, host: 2223, id:"ssh"
    server.vm.provision "shell",
      run: "always",
      inline: "ifconfig eth1 192.168.2.232 netmask 255.255.255.0 up"
    server.vm.provision "shell",
      run: "always",
      inline: "echo 1 | sudo tee -a /proc/sys/net/ipv4/ip_forward"
    server.vm.network "private_network",
      virtualbox__intnet: "vpnproxy-wan",
      ip: "192.168.75.100"
    server.vm.provision "shell",
      inline: "/vagrant/scripts/install.sh"
    server.vm.provision "shell",
      run: "always",
      inline: "nohup /vagrant/vpn-proxy/manage.py " \
              "runserver 192.168.2.232:8080 " \
              "> /var/log/django.log 2>&1 </dev/null & sleep 5"
    # Set up openvpn server
    #(1..2).each do |i|
    #  server.vm.provision "shell",
    #    inline: "echo \"Attempting to create tunnel #{i}\" && " \
    #            "curl -s -X POST -d client=172.17.17.#{2*i} " \
    #            "192.168.2.232:8080/  > /dev/null 2>&1 || echo \"Error..?\""
    #  server.vm.provision "shell",
    #    run: "always",
    #    inline: "curl -s -X POST 192.168.2.232:8080/#{i}/"
    #  server.vm.provision "shell",
    #    run: "always",
    #    inline: "curl -s 192.168.2.232:8080/#{i}/client_script/ " \
    #            "> /vagrant/tmp/proxy#{i}.sh"
    #end
    server.vm.post_up_message = TOPOLOGY
  end

  # Create two `proxy` vm's connected to `server` with each proxy also
  # connected via a private network (same address space) to a `target` server.
  (1..2).each do |i|
    config.vm.define "proxy#{i}" do |proxy|
      proxy.vm.hostname = "proxy#{i}"
      proxy.vm.network :forwarded_port, guest: 22, host: "222#{i+3}".to_i, id:"ssh"
      proxy.vm.network "private_network",
        virtualbox__intnet: "vpnproxy-wan",
        ip: "192.168.75.#{i+100}"
      proxy.vm.network "private_network",
        virtualbox__intnet: "vpnproxy-lan#{i}",
        ip: "10.75.#{74+i}.10"
      proxy.vm.network "private_network",
        virtualbox__intnet: "vpnproxy-lan#{2+i}",
        ip: "10.75.#{76+i}.10"
    #  proxy.vm.provision "shell",
    #    run: "always",
    #    inline: "bash /vagrant/tmp/proxy#{i}.sh"
    end
  end

  # Create two `target` vm's with the same IP on different networks with the
  # same address space, each connected to its corresponding `proxy` vm.
  (1..2).each do |i|
    config.vm.define "target#{i}" do |target|
      target.vm.network :forwarded_port, guest: 22, host: "222#{i+5}".to_i, id:"ssh"
      target.vm.hostname = "target#{i}"
      target.vm.network "private_network",
        virtualbox__intnet: "vpnproxy-lan#{i}",
        ip: "10.75.#{74+i}.75"
    end
  end

  # Create two more `target` vm's, each connected to its corresponding `proxy`
  # vm.
  (1..2).each do |i|
    config.vm.define "target#{2+i}", autostart: false do |target|
      target.vm.hostname = "target#{2+i}"
      target.vm.network "private_network",
        virtualbox__intnet: "vpnproxy-lan#{2+i}",
        ip: "10.75.#{76+i}.75"
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
