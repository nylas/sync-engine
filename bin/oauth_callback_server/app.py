from flask import Flask, request
import logging as log
import urlparse

from inbox.server.config import config, load_config
load_config()

app = Flask(__name__)
log.basicConfig(level=log.DEBUG)

uri = config.get('GOOGLE_OAUTH_REDIRECT_URI', None)
assert uri, 'You must define GOOGLE_OAUTH_REDIRECT_URI'
path = urlparse.urlparse(uri)
CALLBACK_URI = path.path


@app.route(CALLBACK_URI + '/alive')
def alive():
    return 'Yep'


@app.route(CALLBACK_URI)
def index():
    assert 'code' in request.args
    authorization_code = request.args['code']
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Successfull OAuth</title>
    <style type="text/css">
    </style>
    <style type="text/css">
    body,td,div,p,a,font,span
    {font-family: arial, sans-serif; font-size: small;}
        body {margin-top: 2; bgcolor: "#fff"}
        #ogb {margin-bottom: 10px;}
    </style>
</head>

<body>
    <div id="ogb">

    </div>Please copy this code, switch to your application
    and paste it there:<br>
    <form>
        <input id="code" onclick="this.focus();this.select();"
        readonly="readonly" style="width:300px"
        type="text" value="%s">
    </form>
</body>
</html>
    """.strip() % authorization_code


if __name__ == '__main__':

    app_url = '0.0.0.0'
    app_port = 5000

    if not isinstance(app_port, int):
        log.warning("Specified port to listen should be an integer")
        app_port = int(app_port)
    log.info("Starting Flask...")
    app.debug = True

    log.info('Listening on '+app_url+':'+str(app_port)+"/")
    app.run(host=app_url, port=app_port,
            debug=True)
