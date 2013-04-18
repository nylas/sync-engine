# Crispin (working name...)

Crispin is first step towards transcending email.

All of the todos are in [the Asana workspace](https://app.asana.com/0/4983727800919/4983727800919).


## Setup

1. Install [virtualenv](http://www.virtualenv.org/en/latest/), which is just good in general.

2. `git clone --recursive git@github.com:grinich/crispin.git` to get the source and submodules.

2. `cd` into the source and call `virtualenv --no-site-packages .`
   If you're on a Mac, add the `--use-distribute` flag.

3. `source bin/activate` to start virtualenv

4. `pip install -r requirements.txt` to install required packages

5. `pip install -e packages/imaplib2` to install imaplib2

<!-- 

In the figure we might use this to add a custom package location, such as for imaplib2

`pip install -r requirements.txt -f ./packages/imaplib2/dist/`

after running `python setup.py sdist` in the imaplib2 directory

development:  pip install -e packages/imaplib2/

 -->

 5. Right now getting Gmail oauth credentials is manual. Go figure it out and put them in `credentials.py`. 

 6. `app.py`

 7. Open your browser to [http://localhost:8888](http://localhost:8888)
 
 8. Now make that better


<hr/>


## High-level design

This will end up being a very complicated system, so it's important to define reasonable abstractions initially. In general, this will follow the MVC pattern.

### Browser / Client

The client will be a [single page app](http://singlepageappbook.com/single-page.html) in the sense that view updates will not require reloading the page. All templating will be done client-side.

##### UI+view manipulation

Handled by Angular.JS. This will be (hopefully) pure DOM manipulation, and not require lots of javascript for things like animation. Try to do it with [CSS transitions](http://daneden.me/animate/). Obviously some JS will be needed for text formatting, but keep this cleanly separated using Angular's defined abstractions.

##### Data model

Probably native javascript. A lot of this will be heavily cached and take advantage of `localStorage` or the HTML5 file system APIs. Javascript is weird.

Maybe use a framework like [breeze](http://www.breezejs.com/documentation/introduction) for this abstraction.

##### Data sync

Sync will be handled by a transactional system, where the client UI will update immediately and changes will then be "comitted" in the background. After retry, the errors will bubble up to the UI. The UI should *never* block and all operations should be async.

##### Wire protocol (not yet implemented)

Use something like [socket.io](http://socket.io/) for communicating with the server. This isn't a REST app, so there won't be typical routes. Each message should have an action, time, auth, payload, etc. All UI templating will be done on the client.

Right now we're using Tornado, which is just for quick debugging and playing around with UI styles. 

A basic set of actions needs to be defined in order to start building v1.



### Server

##### Web request framework

Since we don't really need any stuff like templating or REST urls, most web frameworks are too heavy. [Diesel](http://diesel.io/) seems like it might be a good choice. This could be custom too.

##### Application logic

Handlers for messages from the client. Some will be just to retreive data, which can hit a DB cache instead of going to IMAP. This will be the main DB access point.

##### Data model logic

Python models similar to the JS client ones. These will be expanded and include a lot of info needed for IMAP operations.

##### IMAP handler

Separate system that deals with connections to IMAP servers, heavily event-based, maintaining and pooling connections. Most IMAP libraries are blocking, which sucks. Currently looking ot using [imaplib2](http://github.com/grinich/imaplib2) or a variant.

A subsystem of this will handle keeping open IDLE messages and communicating new events to the app logic layer, which will push it to connected clients (and eventually mobile notifications). 

##### Database

IMAP is slow as balls so we need to cache pretty much everything. Actual message data rarely (never?) changes on the server, so we can prefetch and store it for super fast access. We probably don't want to do that with attachments or super old messsages.

Pretty much everyone recommends against storing email body in a relational database. They all use flat files on disk and index metadata somewhere for quick access. (Fuck it, maybe Mongo?) 

Punt to Gmail for real search. Client will search as you type locally with cached messages.


