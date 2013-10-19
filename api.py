import logging as log
import json

from models import Contact

class API(object):


    def list_contacts(self):
        # Dummy create and return two contacts
        c = Contact()
        c.name = "John Smith"
        c.email = "john.smth@gmail.com"
        c.google_id  = '01962490143'

        d = Contact()
        d.name = "Jane Smith"
        d.email = "jane.smth@gmail.com"
        d.google_id  = '09123124'

        return [x.cereal() for x in (c, d)]


    def search(self, query):
        # Return a dummy contact
        c = Contact()
        c.name = "John Smith"
        c.email = "john.smth@gmail.com"
        c.google_id  = '01962490143'

        return [c.cereal()]


    def create_contact(self, contact_dict):

        # TODO what should we require
        assert 'name' in contact_dict
        assert 'email' in contact_dict

        # new_contact = Contact()
        # set the parameters
        # commit to db

        return True


    def do_something(self, some_argument):
        return "you said: " + str(some_argument)
