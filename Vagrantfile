# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

TOPOLOGY = <<EOF
      NETWORK TOPOLOGY (RAW)
      ======================

             --------
             |SERVER|
             --------
          192.168.75.100
                 |
       __________|_________
       |        WAN       |
       |                  |
192.168.75.101     192.168.75.102
   --------            --------
   |PROXY1|            |PROXY2|
   --------            --------
  10.75.75.10        10.75.75.10
       |                  |
       | Private networks |
       |  with conflicts  |
       |                  |
  10.75.75.75        10.75.75.75
   ---------          ---------
   |TARGET1|          |TARGET2|
   ---------          ---------
EOF

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # Use ubuntu for all vm's. This would also work with debian/jessie64.
  config.vm.box = "ubuntu/trusty64"

  # Create a `server` vm, connected to 2 proxies.
  config.vm.define "server", primary: true do |server|
    server.vm.hostname = "server"
    server.vm.network "private_network", ip: "192.168.75.100"
    server.vm.post_up_message = TOPOLOGY
  end

  # Create two `proxy` vm's connected to `server` with each proxy also
  # connected via a private network (same address space) to a `target` server.
  (1..2).each do |i|
    config.vm.define "proxy#{i}" do |proxy|
      proxy.vm.hostname = "proxy#{i}"
      proxy.vm.network "private_network", ip: "192.168.75.#{i+100}"
      proxy.vm.network "private_network", ip: "10.75.75.10",
        virtualbox__intnet: "int#{i}"
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
