"""Utility for loading SQLAlchemy model classes and friends. Please see
inbox/models/__init__.py for the explanation of why this is necessary."""


def load_models():
    from inbox.models.account import Account
    from inbox.models.base import MailSyncBase
    from inbox.models.action_log import ActionLog
    from inbox.models.block import Block, Part
    from inbox.models.contact import MessageContactAssociation, Contact
    from inbox.models.calendar import Calendar
    from inbox.models.event import Event
    from inbox.models.folder import Folder, FolderItem
    from inbox.models.message import Message
    from inbox.models.namespace import Namespace
    from inbox.models.search import SearchIndexCursor
    from inbox.models.secret import Secret
    from inbox.models.tag import Tag
    from inbox.models.thread import Thread, TagItem
    from inbox.models.transaction import Transaction
    from inbox.models.when import When, Time, TimeSpan, Date, DateSpan
    exports = [Account, MailSyncBase, ActionLog, Block, Part,
               MessageContactAssociation, Contact, Calendar, Event, Folder,
               FolderItem, Message, Namespace, SearchIndexCursor, Secret, Tag,
               Thread, TagItem, Transaction, When, Time, TimeSpan, Date,
               DateSpan]
    return exports
