# Inbox

[http://www.inboxapp.com](http://www.inboxapp.com)

All of the todos are in [the Asana workspace](https://app.asana.com/0/4983727800919/4983727800919).

The Inbox platform currenly consists of two parts: the Python web server and the Javascript browser client. They communicate mostly over a custom JSON-RPC inspired websocket protocol.

Before you look at the code, please go read ["Worse is
Better"](http://www.jwz.org/doc/worse-is-better.html). We are trying to ship a
product here!

The server usually runs on EC2. Here's how you get it started.


## Setup

We run Ubuntu 10.04 on EC2. You can also do this locally via Vmware Fusion

1. Install [virtualenv](http://www.virtualenv.org/en/latest/).

2. `git clone --recursive git@github.com:inboxapp/inbox.git` to get the source and submodules.

3. `cd` into the source and call `virtualenv --no-site-packages .` which will create a new environment, free of any default python packages that come with Ubuntu

4. `git submodule init && git submodule update` to fetch the subrepos

5. `source bin/activate` to start virtualenv.

6. run `easy_install -U distribute`

7. run `./install_xapian.sh`

8. run `pip install -r requirements.txt`

9. Then copy `config-sample.cfg` to `config.cfg` and change it appropriately for your local MySQL database and hostname.

10. Create the mysql database with 'mysql -uroot -p < tools/create-db.sql' (you'll have to specify your mysql server's root password when prompted).

11. Copy deploy/my.cnf to /etc/my.cnf and restart mysqld.

12. Nginx needs some SSL certificates. Go ask Michael for those, or create your own self-signed ones.

13. Run `sudo nginx -c deploy/nginx.conf -p ./` to start nginx

14. Run `./inboxapp-srv debug` which should start up nicely.

15. Visit your page in a browser and log in!


## Local development

There are a few ways to efficiently develop locally.

If you're only doing client dev work, you can simply clone the repo locally and start a Python webserver to host the static assets by running `sudo python -m SimpleHTTPServer 8888`. You should configure the Wire.js protocol to connect to the production server endpoint by editing `web_client/js/app.js` and changing it to something like `https://dev-01.inboxapp.com:443/wire`. Note that you need the 443 since the `SimpleHTTPServer` doesn't support SSL.

You also need to edit your `/etc/hosts` file to include `127.0.0.1 dev-ui.inboxapp.com` in order for the Google oauth callback to work. Then visit http://dev-ui.inboxapp.com:8888 and voila!

NB: when changing `/etc/hosts` on OS X you might need to run `dscacheutil -flushcache` afterward.


<hr/>

## Style guide and git notes

We'll just be using the [Google Python style guide](http://google-styleguide.googlecode.com/svn/trunk/pyguide.html). No need to reinvent the wheel.

Also, do `git config branch.master.rebase true` in the repo to keep your history nice and clean. You can set this globally using `git config --global branch.autosetuprebase remote`.
