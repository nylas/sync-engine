import fnmatch
import os
import gzip
import time
from email.Parser import Parser
import string
import unicodedata
import email.utils
import hashlib


log_msg = False

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = "\033[1m"

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''


mail_directory = '/Users/mg/gmvault-db/db/'
detach_dir = '/Users/mg/gmvault-db/mail-downloads/'

dupe_counter = {}
attachment_hashes = {}

def main():

    matches = []
    counter = 0

    print 'Scanning messages from: ' + bcolors.BOLD +  mail_directory + bcolors.ENDC
    print 'Saving attachments to: ' + bcolors.BOLD +  detach_dir + bcolors.ENDC

    for root, dirnames, filenames in os.walk(mail_directory):
      for filename in fnmatch.filter(filenames, '*.eml.gz'):

        f = gzip.open(root+'/'+filename, 'rb')
        raw_msg_content = f.read()
        f.close()

        parser = Parser()



        mail = parser.parsestr(raw_msg_content)



        #Check if any attachments at all
        if mail.get_content_maintype() != 'multipart':
            continue


        # we use walk to create a generator so we can iterate on the parts and forget about the recursive headach
        for part in mail.walk():

            # multipart are just containers, so we skip them
            if part.get_content_maintype() == 'multipart':
                continue

            # is this part an attachment ?
            if part.get('Content-Disposition') is None:
                continue

            # HTML type attachments 
            if part.get_content_maintype() == "text/html":
                # print "Multipart has HTML component"
                continue

            if part.get_content_maintype() == "text/plain":
                # print "Multipart has plaintext component"
                continue


            # This is a message so we should parse it
            if part.get_content_type() == 'message/rfc822':
                print bcolors.FAIL + 'Attached file is rfc822 (message)' + bcolors.ENDC

                print part
                # mail2 = parser.parsestr(part)
                # for part in mail2.walk(): print 'Part of attachment: ', part

            # debug
            # continue


            # Also do text/enriched ???

            attachment_filename = part.get_filename()

            if attachment_filename == None: 
                attachment_filename = part["name"]

                # I think part.get_filename() does this
                # attachment_filename = part["filename"]


            if not attachment_filename:

                # Skip inline attachments. (images without filenames, PHP keys, message/rfc822 ,etc)
                if part.get('Content-Disposition') == "inline":
                    print 'Not saving inline file with Content-Type: ', part.get('Content-Type')
                    continue

                attachment_filename = 'part-%03d.%s' % (counter, 'bin')
                counter += 1

                if log_msg:
                    print bcolors.HEADER + bcolors.BOLD + 'NO FILENAME' + bcolors.ENDC + bcolors.ENDC
                    print 'Message from ' + mail["From"] + " at " + root+'/'+filename

                    print 'Content-ID: ',  part.get('Content-ID') 
                    print 'Content-Type: ', part.get('Content-Type')
                    print bcolors.OKBLUE + 'Content-Disposition' + bcolors.ENDC, part.get('Content-Disposition')
            
            # Don't need to log these yet
            # print bcolors.FAIL + "Filename: " + attachment_filename + bcolors.ENDC,
            # print bcolors.OKBLUE + "Filetype: " + part.get('Content-Type') + bcolors.ENDC


            if attachment_filename == "signature.asc":
                print bcolors.HEADER + "Found signature!" + bcolors.ENDC





            payload = part.get_payload(decode=True)

            if payload == None:
                print 'Found attachment with no length.'
                print 'Message from ' + mail["From"] + " at " + root+'/'+filename

                # Not going to save anything so don't even bother making a file
                continue                

            sha = hashlib.sha1()
            sha.update(payload)
            sha_hash = sha.hexdigest()


            #attachment hashes:    file hash => count
            #filename => hashes

            if not attachment_hashes.has_key(sha_hash): 
                attachment_hashes[sha_hash] = 0

            attachment_hashes[sha_hash] += 1

            if attachment_hashes[sha_hash] > 1 :
                print bcolors.WARNING + 'Duplicate file found (' + str(dupe_counter[attachment_filename]) + ') '  + bcolors.ENDC + attachment_filename




            # Primitive sanitizer for filenames
            sanitized_filename = attachment_filename.replace("/", "")

            if sanitized_filename != attachment_filename:
                if log_msg: print '(sanitized: ', sanitized_filename, ')'
                attachment_filename = sanitized_filename


            att_path = os.path.join(detach_dir, attachment_filename)

            #Check if its already there

            if not dupe_counter.has_key(attachment_filename): 
                dupe_counter[attachment_filename] = 0

            if os.path.isfile(att_path) :

                dupe_counter[attachment_filename] += 1

                count = dupe_counter[attachment_filename]

                splitname = os.path.splitext(attachment_filename)
                dupe_attachment_filename = splitname[0] + " (" + str(dupe_counter[attachment_filename]) + ")" + splitname[1]

                print  "Conflicting filename: " + bcolors.BOLD + attachment_filename +bcolors.ENDC + ' => ' +  bcolors.BOLD + dupe_attachment_filename + bcolors.ENDC

                att_path = os.path.join(detach_dir, dupe_attachment_filename)





            # finally write the stuff
            fp = open(att_path, 'wb')

            # md5 = hashlib.md5()
            # with open('myfile.txt','rb') as f: 
            #     for chunk in iter(lambda: f.read(8192), b''): 
            #          md5.update(chunk)
            # return md5.digest()


            fp.write(payload)

            fp.close()


            print bcolors.OKGREEN + 'Saving to: ' + bcolors.ENDC +  att_path
            
            # st = os.stat(fp)

            # atime = st[ST_ATIME] #access time
            # mtime = st[ST_MTIME] #modification time

            # created_time = time.mktime( parse(mail["Date"]).timetuple() ) # no good
            date_tuple = email.utils.parsedate_tz(mail["Date"])
            created_time = time.mktime( date_tuple[:9]  )

            # created_time = time.strptime([:24], "%a, %d %b %Y %H:%M:%S")
            created_time_since_epoch = created_time

            #modify the file timestamp
            os.utime(att_path, (time.mktime(time.gmtime()), created_time_since_epoch) )




    # if emailMessage.is_multipart():
    #     subj = emailMessage.__getitem__('Subject')
    #     print subj

   # matches.append(os.path.join(root, filename))


if __name__=="__main__":
    main()