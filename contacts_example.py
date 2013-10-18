#!/usr/bin/python
#
# Copyright (C) 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__author__ = 'api.jscudder (Jeffrey Scudder)'


import sys
import getopt
import getpass
import atom
import gdata.contacts.data
import gdata.contacts.client


class ContactsSample(object):
  """ContactsSample object demonstrates operations with the Contacts feed."""

  def __init__(self, email, password):
    """Constructor for the ContactsSample object.
    
    Takes an email and password corresponding to a gmail account to
    demonstrate the functionality of the Contacts feed.
    
    Args:
      email: [string] The e-mail address of the account to use for the sample.
      password: [string] The password corresponding to the account specified by
          the email parameter.
    
    Yields:
      A ContactsSample object used to run the sample demonstrating the
      functionality of the Contacts feed.
    """
    self.gd_client = gdata.contacts.client.ContactsClient(source='GoogleInc-ContactsPythonSample-1')
    self.gd_client.ClientLogin(email, password, self.gd_client.source)

  def PrintFeed(self, feed, ctr=0):
    """Prints out the contents of a feed to the console.
   
    Args:
      feed: A gdata.contacts.ContactsFeed instance.
      ctr: [int] The number of entries in this feed previously printed. This
          allows continuous entry numbers when paging through a feed.
    
    Returns:
      The number of entries printed, including those previously printed as
      specified in ctr. This is for passing as an argument to ctr on
      successive calls to this method.
    
    """
    if not feed.entry:
      print '\nNo entries in feed.\n'
      return 0
    for i, entry in enumerate(feed.entry):
      print '\n%s %s' % (ctr+i+1, entry.title.text)
      if entry.content:
        print '    %s' % (entry.content.text)
      for email in entry.email:
        if email.primary and email.primary == 'true':
          print '    %s' % (email.address)
      # Show the contact groups that this contact is a member of.
      for group in entry.group_membership_info:
        print '    Member of group: %s' % (group.href)
      # Display extended properties.
      for extended_property in entry.extended_property:
        if extended_property.value:
          value = extended_property.value
        else:
          value = extended_property.GetXmlBlob()
        print '    Extended Property %s: %s' % (extended_property.name, value)
    return len(feed.entry) + ctr

  def PrintPaginatedFeed(self, feed, print_method):
    """ Print all pages of a paginated feed.
    
    This will iterate through a paginated feed, requesting each page and
    printing the entries contained therein.
    
    Args:
      feed: A gdata.contacts.ContactsFeed instance.
      print_method: The method which will be used to print each page of the
          feed. Must accept these two named arguments:
              feed: A gdata.contacts.ContactsFeed instance.
              ctr: [int] The number of entries in this feed previously
                  printed. This allows continuous entry numbers when paging
                  through a feed.
    """
    ctr = 0
    while feed:
      # Print contents of current feed
      ctr = print_method(feed=feed, ctr=ctr)
      # Prepare for next feed iteration
      next = feed.GetNextLink()
      feed = None
      if next:
        if self.PromptOperationShouldContinue():
          # Another feed is available, and the user has given us permission
          # to fetch it
          feed = self.gd_client.GetContacts(uri=next.href)
        else:
          # User has asked us to terminate
          feed = None

  def PromptOperationShouldContinue(self):
    """ Display a "Continue" prompt.
    
    This give is used to give users a chance to break out of a loop, just in
    case they have too many contacts/groups.
    
    Returns:
      A boolean value, True if the current operation should continue, False if
      the current operation should terminate.
    """
    while True:
      input = raw_input("Continue [Y/n]? ")
      if input is 'N' or input is 'n':
        return False
      elif input is 'Y' or input is 'y' or input is '':
        return True

  def ListAllContacts(self):
    """Retrieves a list of contacts and displays name and primary email."""
    feed = self.gd_client.GetContacts()
    self.PrintPaginatedFeed(feed, self.PrintContactsFeed)

  def PrintGroupsFeed(self, feed, ctr):
    if not feed.entry:
      print '\nNo groups in feed.\n'
      return 0
    for i, entry in enumerate(feed.entry):
      print '\n%s %s' % (ctr+i+1, entry.title.text)
      if entry.content:
        print '    %s' % (entry.content.text)
      # Display the group id which can be used to query the contacts feed.
      print '    Group ID: %s' % entry.id.text
      # Display extended properties.
      for extended_property in entry.extended_property:
        if extended_property.value:
          value = extended_property.value
        else:
          value = extended_property.GetXmlBlob()
        print '    Extended Property %s: %s' % (extended_property.name, value)
    return len(feed.entry) + ctr

  def PrintContactsFeed(self, feed, ctr):
    if not feed.entry:
      print '\nNo contacts in feed.\n'
      return 0
    for i, entry in enumerate(feed.entry):
      if not entry.name is None:
        family_name = entry.name.family_name is None and " " or entry.name.family_name.text
        full_name = entry.name.full_name is None and " " or entry.name.full_name.text
        given_name = entry.name.given_name is None and " " or entry.name.given_name.text
        print '\n%s %s: %s - %s' % (ctr+i+1, full_name, given_name, family_name)
      else:
        print '\n%s %s (title)' % (ctr+i+1, entry.title.text)
      if entry.content:
        print '    %s' % (entry.content.text)
      for p in entry.structured_postal_address:
        print '    %s' % (p.formatted_address.text)
      # Display the group id which can be used to query the contacts feed.
      print '    Group ID: %s' % entry.id.text
      # Display extended properties.
      for extended_property in entry.extended_property:
        if extended_property.value:
          value = extended_property.value
        else:
          value = extended_property.GetXmlBlob()
        print '    Extended Property %s: %s' % (extended_property.name, value)
      for user_defined_field in entry.user_defined_field:
        print '    User Defined Field %s: %s' % (user_defined_field.key, user_defined_field.value)
    return len(feed.entry) + ctr

  def ListAllGroups(self):
    feed = self.gd_client.GetGroups()
    self.PrintPaginatedFeed(feed, self.PrintGroupsFeed)

  def CreateMenu(self):
    """Prompts that enable a user to create a contact."""
    name = raw_input('Enter contact\'s name: ')
    notes = raw_input('Enter notes for contact: ')
    primary_email = raw_input('Enter primary email address: ')

    new_contact = gdata.contacts.data.ContactEntry(name=gdata.data.Name(full_name=gdata.data.FullName(text=name)))
    new_contact.content = atom.data.Content(text=notes)
    # Create a work email address for the contact and use as primary. 
    new_contact.email.append(gdata.data.Email(address=primary_email, 
        primary='true', rel=gdata.data.WORK_REL))
    entry = self.gd_client.CreateContact(new_contact)

    if entry:
      print 'Creation successful!'
      print 'ID for the new contact:', entry.id.text
    else:
      print 'Upload error.'

  def QueryMenu(self):
    """Prompts for updated-min query parameters and displays results."""
    updated_min = raw_input(
        'Enter updated min (example: 2007-03-16T00:00:00): ')
    query = gdata.contacts.client.ContactsQuery()
    query.updated_min = updated_min
    feed = self.gd_client.GetContacts(q=query)
    self.PrintFeed(feed)

  def QueryGroupsMenu(self):
    """Prompts for updated-min query parameters and displays results."""
    updated_min = raw_input(
        'Enter updated min (example: 2007-03-16T00:00:00): ')
    query = gdata.contacts.client.ContactsQuery(feed='/m8/feeds/groups/default/full')
    query.updated_min = updated_min
    feed = self.gd_client.GetGroups(q=query)
    self.PrintGroupsFeed(feed, 0)
   
  def _SelectContact(self):
    feed = self.gd_client.GetContacts()
    self.PrintFeed(feed)
    selection = 5000
    while selection > len(feed.entry)+1 or selection < 1:
      selection = int(raw_input(
          'Enter the number for the contact you would like to modify: '))
    return feed.entry[selection-1]

  def UpdateContactMenu(self):
    selected_entry = self._SelectContact()
    new_name = raw_input('Enter a new name for the contact: ')
    if not selected_entry.name:
      selected_entry.name = gdata.data.Name()
    selected_entry.name.full_name = gdata.data.FullName(text=new_name)
    self.gd_client.Update(selected_entry)

  def DeleteContactMenu(self):
    selected_entry = self._SelectContact()
    self.gd_client.Delete(selected_entry)

  def PrintMenu(self):
    """Displays a menu of options for the user to choose from."""
    print ('\nContacts Sample\n'
           '1) List all of your contacts.\n'
           '2) Create a contact.\n'
           '3) Query contacts on updated time.\n'
           '4) Modify a contact.\n'
           '5) Delete a contact.\n'
           '6) List all of your contact groups.\n'
           '7) Query your groups on updated time.\n'
           '8) Exit.\n')

  def GetMenuChoice(self, max):
    """Retrieves the menu selection from the user.
    
    Args:
      max: [int] The maximum number of allowed choices (inclusive)
      
    Returns:
      The integer of the menu item chosen by the user.
    """
    while True:
      input = raw_input('> ')

      try:
        num = int(input)
      except ValueError:
        print 'Invalid choice. Please choose a value between 1 and', max
        continue
      
      if num > max or num < 1:
        print 'Invalid choice. Please choose a value between 1 and', max
      else:
        return num

  def Run(self):
    """Prompts the user to choose funtionality to be demonstrated."""
    try:
      while True:

        self.PrintMenu()

        choice = self.GetMenuChoice(8)

        if choice == 1:
          self.ListAllContacts()
        elif choice == 2:
          self.CreateMenu()
        elif choice == 3:
          self.QueryMenu()
        elif choice == 4:
          self.UpdateContactMenu()
        elif choice == 5:
          self.DeleteContactMenu()
        elif choice == 6:
          self.ListAllGroups()
        elif choice == 7:
          self.QueryGroupsMenu()
        elif choice == 8:
          return

    except KeyboardInterrupt:
      print '\nGoodbye.'
      return


def main():
  """Demonstrates use of the Contacts extension using the ContactsSample object."""
  # Parse command line options
  try:
    opts, args = getopt.getopt(sys.argv[1:], '', ['user=', 'pw='])
  except getopt.error, msg:
    print 'python contacts_example.py --user [username] --pw [password]'
    sys.exit(2)

  user = ''
  pw = ''
  # Process options
  for option, arg in opts:
    if option == '--user':
      user = arg
    elif option == '--pw':
      pw = arg

  while not user:
    print 'NOTE: Please run these tests only with a test account.'
    user = raw_input('Please enter your username: ')
  while not pw:
    pw = getpass.getpass()
    if not pw:
      print 'Password cannot be blank.'


  try:
    sample = ContactsSample(user, pw)
  except gdata.client.BadAuthentication:
    print 'Invalid user credentials given.'
    return

  sample.Run()


if __name__ == '__main__':
  main()
