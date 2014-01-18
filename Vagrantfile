# -*- mode: ruby -*-
# vi: set ft=ruby :

BOX_NAME = ENV['BOX_NAME'] || "ubuntu"
BOX_URI = ENV['BOX_URI'] || "http://files.vagrantup.com/precise64.box"
VF_BOX_URI = ENV['BOX_URI'] || "http://files.vagrantup.com/precise64_vmware_fusion.box"
AWS_BOX_URI = ENV['BOX_URI'] || "https://github.com/mitchellh/vagrant-aws/raw/master/dummy.box"
AWS_REGION = ENV['AWS_REGION'] || "us-east-1"
AWS_AMI = ENV['AWS_AMI'] || "ami-69f5a900"
AWS_INSTANCE_TYPE = ENV['AWS_INSTANCE_TYPE'] || 't1.micro'

SSH_PRIVKEY_PATH = ENV["SSH_PRIVKEY_PATH"]



$script = <<SCRIPT

# Update remote package metadata.  'apt-get update' is idempotent.
apt-get update -q

cd /vagrant
sudo /bin/sh setup.sh

SCRIPT



Vagrant::Config.run do |config|
  # Setup virtual machine box. This VM configuration code is always executed.
  config.vm.box = BOX_NAME
  config.vm.box_url = BOX_URI

  # Use the specified private key path if it is specified and not empty.
  if SSH_PRIVKEY_PATH
      config.ssh.private_key_path = SSH_PRIVKEY_PATH
  end

  config.ssh.forward_agent = true
end


# Vagrant::VERSION >= "1.1.0" and Vagrant.configure("2") do |config|
#   config.vm.network :private_network, ip: "192.168.10.200"
# end


# Providers were added on Vagrant >= 1.1.0
#
# NOTE: The vagrant "vm.provision" appends its arguments to a list and executes
# them in order.  If you invoke "vm.provision :shell, :inline => $script"
# twice then vagrant will run the script two times.  Unfortunately when you use
# providers and the override argument to set up provisioners (like the vbox
# guest extensions) they 1) don't replace the other provisioners (they append
# to the end of the list) and 2) you can't control the order the provisioners
# are executed (you can only append to the list).  If you want the virtualbox
# only script to run before the other script, you have to jump through a lot of
# hoops.
#
# Here is my only repeatable solution: make one script that is common ($script)
# and another script that is the virtual box guest *prepended* to the common
# script.  Only ever use "vm.provision" *one time* per provider.  That means
# every single provider has an override, and every single one configures
# "vm.provision".  Much saddness, but such is life.
Vagrant::VERSION >= "1.1.0" and Vagrant.configure("2") do |config|
  config.vm.provider :aws do |aws, override|
    username = "ubuntu"
    override.vm.box_url = AWS_BOX_URI
    override.vm.provision :shell, :inline => $script, :args => username
    aws.access_key_id = ENV["AWS_ACCESS_KEY"]
    aws.secret_access_key = ENV["AWS_SECRET_KEY"]
    aws.keypair_name = ENV["AWS_KEYPAIR_NAME"]
    aws.security_groups = ENV["AWS_SECURITY_GROUP"]
    override.ssh.username = username
    aws.region = AWS_REGION
    aws.ami    = AWS_AMI
    aws.instance_type = AWS_INSTANCE_TYPE
  end

  config.vm.provider :rackspace do |rs, override|
    override.vm.provision :shell, :inline => $script
    rs.username = ENV["RS_USERNAME"]
    rs.api_key  = ENV["RS_API_KEY"]
    rs.public_key_path = ENV["RS_PUBLIC_KEY"]
    rs.flavor   = /512MB/
    rs.image    = /Ubuntu/
  end

  config.vm.provider :vmware_fusion do |f, override|
    override.vm.box_url = VF_BOX_URI
    override.vm.synced_folder ".", "/vagrant", disabled: true
    override.vm.provision :shell, :inline => $script
    f.vmx["displayName"] = "docker"
  end

  config.vm.provider :virtualbox do |vb, override|
    override.vm.provision :shell, :inline => $vbox_script
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
    vb.customize ["modifyvm", :id, "--natdnsproxy1", "on"]
    vb.customize ["modifyvm", :id, "--memory", 1024]
  end
end

# If this is a version 1 config, virtualbox is the only option.  A version 2
# config would have already been set in the above provider section.
Vagrant::VERSION < "1.1.0" and Vagrant::Config.run do |config|
  config.vm.provision :shell, :inline => $vbox_script
end
