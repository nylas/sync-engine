# Inbox

email, refined.

[http://www.inboxapp.com](http://www.inboxapp.com)

All of the todos are in [the Asana workspace](https://app.asana.com/0/4983727800919/4983727800919).


## Setup

1. Install [virtualenv](http://www.virtualenv.org/en/latest/), which is just good in general.

2. `git clone --recursive git@github.com:inboxapp/inbox.git` to get the source and submodules.

3. `cd` into the source and call `virtualenv --no-site-packages .`

4. `git submodule init && git submodule update`

5. `source bin/activate` to start virtualenv

6. `python setup.py develop` to install required packages

Also need to install libevent and then gevent.

7. Add the following to `/etc/hosts`

    # InboxApp
    127.0.0.1   www.inboxapp.com
    127.0.0.1   inboxapp.com

On my mac I had to run `dscacheutil -flushcache` afterward.

8. Install nginx > 1.4 and start it using `sudo nginx -c deploy/nginx.conf -p ./`

8.5 Install xapian using `sudo packages/install_xapian.sh`

9. run `./inbox start`. This defaults to port 8888.

10. Open your browser to [http://localhost:8888](http://localhost:8888)

12. Now make that better


<hr/>

## Style guide and git notes

We'll just be using the [Google Python style guide](http://google-styleguide.googlecode.com/svn/trunk/pyguide.html). No need to reinvent the wheel.

Also, do `git config branch.master.rebase true` in the repo to keep your history nice and clean. You can set this globally using `git config --global branch.autosetuprebase remote`.
