from collections import namedtuple
import os
import ntpath

from flask import render_template, Blueprint, redirect, url_for
import markdown

from inbox.server.log import get_logger
log = get_logger(purpose='api')


tmpl_dir = os.path.join(os.path.dirname(
    os.path.abspath(__file__)),
    'templates')

static_dir = os.path.join(os.path.dirname(
    os.path.abspath(__file__)),
    'static')

docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../docs')

app = Blueprint(
    'docs',
    __name__,
    url_prefix='/docs',
    template_folder=tmpl_dir,
    static_folder=static_dir)


DocPage = namedtuple("DocPage", "anchor title content")


# http://pythonhosted.org/Markdown/extensions/
md = markdown.Markdown(extensions=[
    'fenced_code',
    'tables',
    'codehilite(guess_lang=False)',
    'smart_strong',
    'meta',
    'nl2br',
    'sane_lists',
    'headerid(level=3)',
    'wikilinks(base_url=/d/, end_url=)',
    'smarty'])


@app.route('/<slug>')
def catch_all(slug):
    return redirect(url_for(".homepage"))

@app.route("/")
def homepage():

    docs = {}
    for root, _, files in os.walk(docs_dir):
        for f in files:
            fullpath = os.path.join(root, f)
            with open(fullpath, 'r') as f:

                contents = f.read().decode('utf8')
                html = md.convert(contents)
                if 'skipdoc' not in md.Meta:
                    no_ext = ntpath.basename(f.name).split('.')[0]
                    docs[no_ext] = \
                        DocPage(no_ext.split('_')[1],
                                md.Meta['title'][0],
                                html)

    # Sort display order based on filename
    docs = [docs[k] for k in sorted(docs)]

    return render_template(
        'docs.html',
        docs=docs,
        title='Inbox API documentation')
