# Inbox

email, refined.

[http://www.inboxapp.com](http://www.inboxapp.com)

All of the todos are in [the Asana workspace](https://app.asana.com/0/4983727800919/4983727800919).


## Setup

1. Install [virtualenv](http://www.virtualenv.org/en/latest/), which is just good in general.

2. `git clone --recursive git@github.com:inboxapp/inbox.git` to get the source and submodules.

3. Right now getting Gmail oauth credentials is manual. Go figure it out and put them in `credentials.py`.

<!-- 4. `cd` into the source and call `./inbox install`. This will also start the server. You can later start it using `./inbox start`.
 -->

4. `cd` into the source and call `virtualenv --no-site-packages .`
   If you're on a Mac, add the `--distribute` flag.

5. `source bin/activate` to start virtualenv

6. `pip install -r requirements.txt` to install required packages

Also need to install libevent and then gevent.

7. run `./inbox start`. This defaults to port 8888.

7. Open your browser to [http://localhost:8888](http://localhost:8888)

8. Now make that better


<hr/>

## Style guide and git notes

We'll just be using the [Google Python style guide](http://google-styleguide.googlecode.com/svn/trunk/pyguide.html). No need to reinvent the wheel.

Also, do `git config branch.master.rebase true` in the repo to keep your history nice and clean. You can set this globally using `git config --global branch.autosetuprebase remote`.
