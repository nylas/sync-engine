"""
Monocle - The Inbox Admin Dashboard

Provides mailsync progress and health information for monitoring purposes.

Dashboard information:
---------------------

For all authed accounts (i.e. accounts we have a record of), we track -

'status': {0, 1} - if the sync is Active/ Inactive
(We will eventually distinguish between Stopped vs. Killed instead of Inactive)

For each account, we also track the following per-folder metrics -

state: {Polling, Initial, Finished, None} - state the folder sync is in
type: {New, Resumed} - If the sync was resumed rather than freshly started;
                       relevant in state 'initial' only.
Num messages on remote + when it was calculated
Num messages updated + when it was calculated
Num messages deleted + when it was calculated
Num messages to download + when it was calculated
Num downloaded since then
Num left to download + when it was calculated.

Dashboard implementation:
------------------------

The dashboard is implemented as a Flask app which queries the database for
data.

The app is contained in ./app.py and the API it uses to talk to the database
is in inbox.mailsync.reporting

"""
