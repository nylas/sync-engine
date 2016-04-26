SMTP_ERRORS = {
    421: {
        "4.4.5": (503, "Server busy, try again later."),
        "4.7.0": (429, "Our system has detected an unusual rate of unsolicited "
                       "mail originating from your IP address. To protect our "
                       "users from spam, mail sent from your IP address has "
                       "been temporarily blocked."),
        "4.7.2": (429, "Server busy, try again later."),
    },
    450: {
        "4.2.1": (429, "The user you are trying to contact is receiving mail "
                       "at a rate that prevents additional messages from being"
                       " delivered. Please resend your message at a later time."),
        "4.3.0": (429, "Mail server temporarily rejected message."),
        "4.7.1": (429, "Mail server temporarily rejected message."),
    },
    451: {
        "4.3.5": (429, "Mail server temporarily rejected message."),
        "4.7.1": (429, "Mail server temporarily rejected message."),
    },
    452: {
        "4.5.3": (402, "Your message has too many recipients"),
    },
    454: {
        "4.7.0": (429, "Cannot authenticate due to temporary system problem. "
                       "Try again later.")
    },
    522: {
        "5.7.1": (402, "Recipient address rejected."),
    },
    530: {
        "5.7.0": (402, "Recipient address rejected"),
    },
    535: {
        "5.7.1": (429, "Please log in to Gmail with your web browser and "
                       "try again."),
    },
    550: {
        "5.1.1": (402, "The email account that you tried to reach does not "
                       "exist. Please try double-checking the recipient's "
                       "email address for typos or unnecessary spaces."),
        "5.2.1": (402, "The email account that you tried to reach is disabled."),
        "5.3.2": (429, "Server busy, try again later."),
        "5.4.5": (429, "Daily sending quota exceeded"),
        "5.4.6": (429, "Mail server temporarily rejected message."),
        "5.7.0": (402, "Mail relay denied."),
        "5.7.1": (429, "Daily sending quota exceeded"),

        "This message was classified as SPAM and may not be delivered.": (402,
            "Message blocked due to spam content in the message."),
        "exceeded recipient rate limit": (429, "Daily email quota for this "
                                               "address exceeded."),
        "has exceeded its 24-hour sending limit.": (429, "Daily email quota for this "
                                                         "address exceeded.")

    },
    552: {
        "5.2.3": (402, "Message too large"),
        "5.3.4": (402, "Message too large"),
        "5.7.0": (402, "Message content rejected for security reasons"),
        "5.7.1": (402, "Message content rejected for security reasons"),
    },
    553: {
        "5.1.2": (402, "Unable to find recipient domain. Please check for any "
                       "spelling errors, and make sure you didn't enter any "
                       "spaces, periods, or other punctuation after the "
                       "recipient's email address."),
        "5.7.1": (402, "Sender address rejected"),
    },
    554: {
        "5.6.0": (402, "Mail message is malformed. Not accepted."),
        "5.7.1": (402, "Message blocked due to spam content in the message."),
    }
}
