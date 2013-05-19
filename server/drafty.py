
    @connected
    # TODO this shit is broken
    def create_draft(self, message_string):
        log.info('Adding test draft..')
        self.imap_server.append("[Gmail]/Drafts",
                    str(email.message_from_string(message_string)))
        log.info("Done creating test draft.")


