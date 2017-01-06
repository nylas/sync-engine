"""Drop Contact foreign keys

Revision ID: c48fc8dea1b
Revises: 23ff7f0b506d
Create Date: 2016-09-13 17:29:27.783566

"""

# revision identifiers, used by Alembic.
revision = 'c48fc8dea1b'
down_revision = '4265dc58eec6'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE contact"
                      " DROP FOREIGN KEY contact_ibfk_1"))

    conn.execute(text("ALTER TABLE phonenumber"
                      " DROP FOREIGN KEY phonenumber_ibfk_1"))

    conn.execute(text("ALTER TABLE messagecontactassociation"
                      " DROP FOREIGN KEY messagecontactassociation_ibfk_1"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE contact"
                      " ADD CONSTRAINT contact_ibfk_1 FOREIGN KEY"
                      " (namespace_id) REFERENCES namespace(id)"))

    conn.execute(text("ALTER TABLE phonenumber"
                      " ADD CONSTRAINT phonenumber_ibfk_1 FOREIGN KEY"
                      " (contact_id) REFERENCES contact(id)"))

    conn.execute(text("ALTER TABLE messagecontactassociation"
                      " ADD CONSTRAINT messagecontactassociation_ibfk_1"
                      " FOREIGN KEY (contact_id) REFERENCES contact(id)"))
