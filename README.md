# Inbox

[http://www.inboxapp.com](http://www.inboxapp.com)

All of the todos are in [the Asana workspace](https://app.asana.com/0/4983727800919/4983727800919).

The Inbox platform currenly consists of two parts: the Python web server and the Javascript browser client. They communicate over a custom JSON-RPC inspired websocket protocol.

Before you look at the code, please go read [Worse is Better](http://www.jwz.org/doc/worse-is-better.html). Kindly send all trolling comments to `/dev/null`.

## Set up

The server can run in a variety of environments. In production, we run it on EC2 instances. For development, you can create a local virtual machine. Here's how to get set up.

1. [Install VirtualBox](https://www.virtualbox.org/wiki/Downloads)

2. [Install Vagrant](http://downloads.vagrantup.com/)

3. `git clone git@github.com:inboxapp/inbox-server.git`

4. `cd inbox-server`

5. `vagrant up`

    Feel free to check out the `Vagrantfile` while this starts up. It exposes a few ports and creates a host-only network for the VM at `192.168.10.200`.

6. `vagrant ssh`

    At this point you should be SSH'd into a shiny new Ubuntu 10.04 VM. The `inbox-server` directory you started with should be synced to `/vagrant`.

    We use [docker](http://www.docker.io/) to package Inbox with its depdencies. The next steps will create a new container for development.

7. `cd /vagrant`

8. `docker build -t "inboxapp/inbox-server" .`

    This will take a minute or two. Grab a snickers and [read more about docker](https://www.docker.io/learn_more/).

9. Next, we'll start a shell in the docker container and stay attached.

    `docker run -v /vagrant/:/srv/inboxapp-dev/ -i -t -p 80:5000 1bcb8a95dc72 /bin/bash`

    This command also shares the `/vagrant` directory with the container (so you can keep editing files from your local filesystem) and exposes port 5000 of the container.

10. `cd /srv/inboxapp-dev`

11. `pip install -e inbox-server` to avoid path hacks.

12. `./inboxapp-srv debug`

13. In order for the Google oauth callback to work, you need to edit your local system's `/etc/hosts` file to include the line:

    `192.168.10.200 dev-localhost.inboxapp.com`

And voila! Visit [http://dev-localhost.inboxapp.com]([http://dev-localhost.inboxapp.com) in your browser!


Note that on OS X you might need to run `dscacheutil -flushcache` afterward to flush cached DNS records.


## Production

We want to ship Inbox as a packaged docker container, so it shouldn't contain custom Nginx stuff or SSL certs. This should be a separate package.

Right now Flask handles both static files and upgrading to HTTP 1.1, which is ok for development.



<hr/>

## Style guide and git notes

We'll just be using the [Google Python style guide](http://google-styleguide.googlecode.com/svn/trunk/pyguide.html). No need to reinvent the wheel.

Also, do `git config branch.master.rebase true` in the repo to keep your history nice and clean. You can set this globally using `git config --global branch.autosetuprebase remote`.
