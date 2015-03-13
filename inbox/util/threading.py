# -*- coding: utf-8 -*-
# A simple tree-based threading algorithm. It takes as input a list of messages
# and builds a reference tree using only the message-id, in-reply-to references
# and received-date headers.
#
# Here's the algo stages:
#
# 1. Sort the messages list by received_date. This is to make sure that we
#    insert the messages in the tree in the right order, because the algo
#    does not tolerate weird input (i.e: a parent message received after
#    one of its replies -- thankfully this does not happen often in the real
#    world. If it does get an email server that does not go down
#    every other day).
#
# 2. Insert the messages in a tree, starting from the first. The algo tries
#    to "house" a child next to its direct parent, as specified in its
#    in-reply-to/references. If it's unable to find the parent, it will
#    look for the closest reference. If there's no reference found,
#    it will try to find the closest message by reception date.
#
# 3. Traverse the tree in level-order. Why level-order? Because in this case
#           A
#          / \
#         B   C
#        /
#       D
#    it makes more sense to have the thread be A-B-C-D than A-B-D-C

from inbox.sqlalchemy_ext.util import safer_yield_per
from inbox.models.thread import Thread
from sqlalchemy import desc
from inbox.util.misc import cleanup_subject


MAX_THREAD_LENGTH = 500


class MessageTree(object):
    def __init__(self, message):
        self.children = []  # Note: Children are sorted by received_date
        self.message = message

    def __str__(self):
        s = "Value: %s\n" % str(self.message)
        if self.children != []:
            for child in self.children:
                s += "\t" + str(child)
        return s

    def find_by_message_id(self, message_id):
        if self.message.message_id_header == message_id:
            return self
        else:
            for child in self.children:
                found = child.find_by_message_id(message_id)
                if found:
                    return found

            return None

    def insert_child(self, message):
        self.children.append(message)
        sorted(self.children, key=lambda x: x.message.received_date)

    def insert_message(self, message):
        # Are there references? This includes the in-reply-to
        # header.
        if message.references and len(message.references) > 0:
            # Walk up the reference chain
            for reference in reversed(message.references):
                found = self.find_by_message_id(reference)
                if found:
                    mt = MessageTree(message)
                    found.insert_child(mt)
                    return

        # if there's nothing we can only take an educated guess
        # append the message next to the closest message in time.
        if len(self.children) > 0:
            prior_messages = filter(lambda x: x.message.received_date <
                                          message.received_date, self.children)
            # Pick the first message. Message choice doesn't really matter
            # because we're going to traverse the tree in level-order. We
            # just want a ballpark here.
            if len(prior_messages) > 0:
                prior_messages[0].insert_message(message)
            else:
                # there are no messages prior to this one. Insert
                # directly under parent.
                mt = MessageTree(message)
                self.insert_child(mt)
            return
        else:  # tree with no children
            mt = MessageTree(message)
            self.insert_child(mt)
            return

    def level_order_traversal(self, nodes):
        l = [node.message for node in nodes]
        queue = []
        for node in nodes:
            queue.extend(node.children)

        if len(queue) > 0:
            l.extend(self.level_order_traversal(queue))
        return l

    def as_list(self):
        """traverse the tree in level-order and return a list"""
        return self.level_order_traversal([self])


def thread_messages(messages_list):
    """Order a list of messages in a conversation (à la gmail)"""
    msgs_by_date = sorted(messages_list, key=lambda x: x.received_date)
    root = MessageTree(msgs_by_date[0])
    for msg in msgs_by_date[1:]:
        root.insert_message(msg)
    return root.as_list()


def fetch_corresponding_thread(db_session, namespace_id, message):
    """fetch a thread matching the corresponding message. Returns None if
       there's no matching thread."""
    # FIXME: for performance reasons, we make the assumption that a reply
    # to a message always has a similar subject. This is only
    # right 95% of the time.
    clean_subject = cleanup_subject(message.subject)
    threads = db_session.query(Thread).filter(
        Thread.namespace_id == namespace_id,
        Thread._cleaned_subject == clean_subject). \
        order_by(desc(Thread.id))

    for thread in safer_yield_per(threads, Thread.id, 0, 100):
        for match in thread.messages:
            # A lot of people BCC some address when sending mass
            # emails so ignore BCC.
            match_bcc = match.bcc_addr if match.bcc_addr else []
            message_bcc = message.bcc_addr if message.bcc_addr else []

            match_emails = [t[1] for t in match.participants
                            if t not in match_bcc]
            message_emails = [t[1] for t in message.participants
                              if t not in message_bcc]

            # A conversation takes place between two or more persons.
            # Are there more than two participants in common in this
            # thread? If yes, it's probably a related thread.
            match_participants_set = set(match_emails)
            message_participants_set = set(message_emails)

            if len(match_participants_set & message_participants_set) >= 2:
                # No need to loop through the rest of the messages
                # in the thread
                if len(thread.messages) >= MAX_THREAD_LENGTH:
                    break
                else:
                    return match.thread

            # handle the case where someone is self-sending an email.
            if not message.from_addr or not message.to_addr:
                return

            match_from = [t[1] for t in match.from_addr]
            match_to = [t[1] for t in match.from_addr]
            message_from = [t[1] for t in message.from_addr]
            message_to = [t[1] for t in message.to_addr]

            if (len(message_to) == 1 and message_from == message_to and
                    match_from == match_to and message_to == match_from):
                # Check that we're not over max thread length in this case
                # No need to loop through the rest of the messages
                # in the thread.
                if len(thread.messages) >= MAX_THREAD_LENGTH:
                    break
                else:
                    return match.thread

    return
