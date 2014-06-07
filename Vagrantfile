# -*- mode: ruby -*-
# vi: set ft=ruby :

# Stripped-down Vagrantfile for development


Vagrant::Config.run do |config|

  config.vm.box = 'ubuntu'

  config.provider :vmware_fusion do |vmware|
    config.vm.box_url = "http://files.vagrantup.com/trusty64_vmware.box"
  end
  config.provider :virtualbox do |vb|
    vb.box_url = "http://files.vagrantup.com/trusty64.box"
  end

  config.ssh.forward_agent = true

  config.vm.customize [
    'modifyvm', :id,
    "--natdnshostresolver1", "on",
    "--natdnsproxy1", "on",
    "--memory", 1024
  ]

  # config.vm.provision :shell, :inline => "apt-get update -q && cd /vagrant && /bin/sh setup.sh"
end

Vagrant.configure("2") do |config|
  config.vm.network "forwarded_port", guest: 5000, host: 5000
  config.vm.network "forwarded_port", guest: 8000, host: 8000
  config.vm.network "forwarded_port", guest: 5555, host: 5555
  config.vm.network "forwarded_port", guest: 30000, host:30000

  # This will share any folder in the parent directory that
  # has the name share-*
  # It mounts it at the root without the 'share-' prefix
  share_prefix = "share-"
  Dir['../*/'].each do |fname|
    basename = File.basename(fname)
    if basename.start_with?(share_prefix)
      mount_path = "/" + basename[share_prefix.length..-1]
      puts "Mounting share for #{fname} at #{mount_path}"
      config.vm.synced_folder fname, mount_path
    end
  end
end
