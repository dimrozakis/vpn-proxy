# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  config.vm.box = "ubuntu/trusty64"

  config.vm.define "server", primary: true do |server|
    server.vm.hostname = "server"
    server.vm.network "private_network", ip: "192.168.75.100"
  end

  (1..2).each do |i|
    config.vm.define "proxy#{i}" do |proxy|
      proxy.vm.hostname = "proxy#{i}"
      proxy.vm.network "private_network", ip: "192.168.75.#{i+100}"
      proxy.vm.network "private_network", ip: "10.75.75.10",
        virtualbox__intnet: "int#{i}"
    end
  end

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

  config.vm.provision "shell",
    run: "always",
    inline: "cd /tmp/ && ln -sf /etc/hostname index.html ; " \
            "nohup python -m SimpleHTTPServer 80 >/dev/null 2>&1 </dev/null &"

end
