#!/bin/bash
set -e

# If you're using Vagrant, install the plugin
# vagrant plugin install vagrant-aws

# And set these:

# export AWS_ACCESS_KEY=xxx
# export AWS_SECRET_KEY=xxx
# export AWS_KEYPAIR_NAME=xxx
# export SSH_PRIVKEY_PATH=xxx
# export AWS_SECURITY_GROUP="quick-start-1"
# export AWS_REGION="us-west-2"
# export AWS_AMI="ami-6aad335a"
# export AWS_INSTANCE_TYPE="t1.micro"

# vagrant up --provider=aws


# export PACKER_LOG=1
# rm packer_virtualbox_virtualbox.box || true
# packer build -only=virtualbox packer.json
# vagrant box remove vagrant_machine || true
# vagrant box add vagrant_machine packer/packer_virtualbox_virtualbox.box


packer build \
    -var 'aws_access_key=AKIAJCPMVLGARHTALPRQ' \
    -var 'aws_secret_key=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' \
    -var 'do_api_key=263927ce54ae7e8315a4ce2bb6df5fa0' \
    -var 'do_client_id=2335915dfcbca5cfaa0689f10a92be45' \
    packer.json
