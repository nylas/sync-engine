# -*- mode: ruby -*-
# vi: set ft=ruby :

# Stripped-down Vagrantfile for development


# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu/precise64"

  config.vm.provider :virtualbox do |vbox, override|
    vbox.memory = 1024
    vbox.cpus = 2
  end

  config.vm.provider :vmware_fusion do |vmware, override|
    override.vm.box = "hashicorp/precise64"
    vmware.vmx["memsize"] = "1024"
    vmware.vmx["numvcpus"] = "1"
  end

  config.ssh.forward_agent = true

  # config.vm.customize [
  #   'modifyvm', :id,
  #   "--natdnshostresolver1", "on",
  #   "--natdnsproxy1", "on",
  # ]
  config.vm.network "private_network", ip: "192.168.10.200"
  config.vm.provision :shell, :inline => "apt-get update -q && cd /vagrant && ./setup.sh"

  # Share ports 5000 - 5009
  10.times do |n|
    config.vm.network "forwarded_port", guest: 5000+n, host: 5000+n, host_ip: "127.0.0.1"
  end

  config.vm.network "forwarded_port", guest: 8000, host: 8000, host_ip: "127.0.0.1"
  config.vm.network "forwarded_port", guest: 5555, host: 5555, host_ip: "127.0.0.1"
  config.vm.network "forwarded_port", guest: 9200, host: 9200, host_ip: "127.0.0.1"

  # This will share any folder in the parent directory that
  # has the name share-*
  # It mounts it at the root without the 'share-' prefix
  here = File.dirname(__FILE__)
  share_prefix = "share-"
  Dir['%s/../%s*' % [here, share_prefix]].each do |fname|
    fname = File.absolute_path(fname)
    if File.directory?(fname)
      basename = File.basename(fname)
      mount_path = "/" + basename[share_prefix.length..-1]
      puts "Mounting share for #{fname} at #{mount_path}"
      config.vm.synced_folder fname, mount_path
    end
  end

  # See: https://stackoverflow.com/questions/14715678/vagrant-insecure-by-default
  unless (Gem::Version.new(Vagrant::VERSION) >= Gem::Version.new('1.7.0') ||
          Vagrant.has_plugin?("vagrant-rekey-ssh"))
    warn "------------------- SECURITY WARNING -------------------"
    warn "Vagrant versions older than 1.7 are insecure by default."
    warn "Please upgrade Vagrant to 1.7.0 or newer, or run:"
    warn "    vagrant plugin install vagrant-rekey-ssh"
    warn "--------------------------------------------------------"
  end
end

# Local Vagrantfile overrides.  See Vagrantfile.local.example for examples.
Dir.glob('Vagrantfile.local.d/*').sort.each do |path|
  load path
end
Dir.glob('Vagrantfile.local').sort.each do |path|
  load path
end
