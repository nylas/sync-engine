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

import re


def cleanup_subject(subject_str):
    """Clean-up a message subject-line.
    For instance, 'Re: Re: Re: Birthday party' becomes 'Birthday party'"""
    if subject_str is None:
        return ''
    # TODO consider expanding to all
    # http://en.wikipedia.org/wiki/List_of_email_subject_abbreviations
    cleanup_regexp = "(?i)^((re|fw|fwd|aw|wg):\s*)+"
    return re.sub(cleanup_regexp, "", subject_str)


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
