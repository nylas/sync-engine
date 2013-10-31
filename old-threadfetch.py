
@connected
def fetch_threads(self, folder_name):

    # Returns a list of Threads.
    def messages_to_threads(messages):
        # Group by thread id
            if m.thread_id not in threads.keys():
                new_thread = MessageThread()
                new_thread.thread_id = m.thread_id
                threads[m.thread_id] = new_thread
            t = threads[m.thread_id]
            t.messages.append(m)  # not all, only messages in folder_name
        return threads.values()

    # Get messages in requested folder
    msgs = self.fetch_headers(folder_name)


    log.info("For %i messages, found %i threads total." % (len(msgs), len(threads)))
    self.select_allmail_folder() # going to fetch all messages in threads

    thread_ids = [t.thread_id for t in threads]

    # The boolean IMAP queries use reverse polish notation for
    # the query parameters. imaplib automatically adds parenthesis
    criteria = 'X-GM-THRID %i' % thread_ids[0]
    if len(thread_ids) > 1:
        for t in thread_ids[1:]:
            criteria = 'OR ' + criteria + ' X-GM-THRID %i' % t

    log.info("Expanded to %i messages for %i thread IDs." % (len(all_msg_uids), len(thread_ids)))

    all_msgs = self.fetch_headers_for_uids(self.all_mail_folder_name(), all_msg_uids)
    all_threads = messages_to_threads(all_msgs)

    log.info("Returning %i threads with total of %i messages." % (len(all_threads), len(all_msgs)))

    return all_threads