from flask import g, Blueprint, current_app
from sqlalchemy.orm.exc import NoResultFound

from inbox.server.models.tables.base import User
from inbox.server.models.kellogs import jsonify

from err import err


app = Blueprint('user_api', __name__, url_prefix='/u/<public_user_id>')


@app.url_value_preprocessor
def pull_lang_code(endpoint, values):
    g.public_user_id = values.pop('public_user_id').lower()


@app.before_request
def auth():
    g.log = current_app.logger
    # TODO implement namespace + auth token check
    g.log.error("Havent implemented namespace auth!")


@app.route('')
def users_api():
    """ Gets user objects"""

    g.log.warning("DANGER THIS API CALL IS NOT SECURE.")

    if g.public_user_id == 'all':
        all_users = g.db_session.query(User).all()
        return jsonify(all_users)

    try:
        user = g.db_session.query(User).filter(
            User.public_id == g.public_user_id).one()
        return jsonify(user)

    except NoResultFound:
        return err(
            404,
            "Couldn't find user with id {0}".format(
                g.public_user_id, g.namespace_id))


@app.route('/logout')
def logout():
        # TODO expire token for this specific user + dev
    raise NotImplementedError
