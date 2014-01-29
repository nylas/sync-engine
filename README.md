# Inbox

#### The open source email toolkit.


Inbox is a set of tools to make it simple and quick to develop apps and services on top of email. It consists of:

- IMAP sync engine
- Gmail OAuth authentication
- MIME parsing and decoding
- Full text search indexing
- Queryable metadata store
- Full message body storage including attachments
- All UTF-8 and JSON sanitized
- Contacts list sync


These features are exposed via clean APIs through ZeroRPC services. See the `/examples` folder for details.



## Getting Started

You can run Inbox almost anywhere. We've successfuly built images for Docker, VMware Fusion, VirtualBox, AWS, and DigitalOcean. The easiest way to get started is to install from source within VirtualBox. 


### Install from source

Here's how to set up a development environment:

1. [Install VirtualBox](https://www.virtualbox.org/wiki/Downloads)

2. [Install Vagrant](http://downloads.vagrantup.com/)

3. `git clone git@github.com:inboxapp/inbox.git`

4. `cd inbox`

5. `vagrant up`

    Feel free to check out the `Vagrantfile` while this starts up. It creates a host-only network for the VM at `192.168.10.200`.

6. `vagrant ssh`

    At this point you should be SSH'd into a shiny new Ubuntu 12.04 VM. The
    `inbox` directory you started with should be synced to `/vagrant`.

    If not, run `vagrant reload` and `vagrant ssh` again. You should see the
    shared folder now.

7. `cd /vagrant`

8. `./setup.sh` to install depdencies and create databases

8. `sudo ./inbox debug`

And voila! Auth an account via the commandline and start syncing:

    `sudo ./inbox auth ben.bitdiddle1861@gmail.com`
    `sudo ./inbox sync start ben.bitdiddle1861@gmail.com`

## Contributing

We'd love your help making Inbox better. Join the [Google
Group](groups.google.com/group/inbox-dev) for project updates and feature
discussion.

We try to stick with pep8 and the [Google Python style
guide](http://google-styleguide.googlecode.com/svn/trunk/pyguide.html).

#### Random notes

You should do `git config branch.master.rebase true` in the repo to keep your
history nice and clean. You can set this globally using `git config --global branch.autosetuprebase remote`.
