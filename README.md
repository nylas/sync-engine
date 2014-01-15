# Inbox

[http://www.inboxapp.com](http://www.inboxapp.com)

Before you look at the code, please go read [Worse is
Better](http://www.jwz.org/doc/worse-is-better.html).

While you're at it, please also read Ryan Dahl's
[rant](https://gist.github.com/cookrn/4015437#file-rant-md).

Now take a deep breath.

Let's begin.

## Set up

The Inbox platform consists of a handful of ZeroRPC-based services that run
on one or more servers. For development, we run them all on a VM. For
production, they run in packaged docker containers to your cloud provider of
choice or private servers.

Here's how to set up a development environment:

1. [Install VirtualBox](https://www.virtualbox.org/wiki/Downloads)

2. [Install Vagrant](http://downloads.vagrantup.com/)

3. `git clone git@github.com:inboxapp/inbox.git`

4. `cd inbox`

5. `vagrant up`

    Feel free to check out the `Vagrantfile` while this starts up. It creates a
    host-only network for the VM at `192.168.10.200`.

6. `vagrant ssh`

    At this point you should be SSH'd into a shiny new Ubuntu 12.04 VM. The
    `inbox` directory you started with should be synced to `/vagrant`.

7. `cd /vagrant`

8. `sudo ./setup_hack.sh`

11. `sudo pip install -e src` to avoid path hacks.

12. `sudo ./inbox debug`

And voila! Auth an account via the commandline to start syncing:

    `sudo ./inbox auth spang@inboxapp.com`

<hr/>

## Style guide and git notes

We'll just be using the [Google Python style
guide](http://google-styleguide.googlecode.com/svn/trunk/pyguide.html). No need
to reinvent the wheel.

Also, do `git config branch.master.rebase true` in the repo to keep your
history nice and clean. You can set this globally using `git config --global
branch.autosetuprebase remote`.
