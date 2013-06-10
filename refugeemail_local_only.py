#!/usr/bin/env python3
'''Refugeemail - An email-transfer client, allowing users to ditch spyware-rich
services like Gmail for servers in countries with better human rights.'''

import imapclient
import sys
import os
import json
import argparse
import getpass
import mailbox

def _chunks(l, n):
    "Yield successive n-sized chunks from l."
    for i in range(0, len(l), n): yield l[i:i+n]

def _uniquify(seq):
    '''This is a fast, order-preserving function for removing duplicates
    from a sequence/list, by "Dave Kirby"
    Found here: http://www.peterbe.com/plog/uniqifiers-benchmark'''
    seen = set()
    return [x for x in seq if x not in seen and not seen.add(x)]

class DumbMailClient:
    def __init__(self, host, port, username, password, ssl = True):
        self.server = imapclient.IMAPClient(host, port=port, use_uid=True, ssl = ssl)
        self.server.login(username, password)
        # Better to have timezone when appending?
        self.server.normalise_times = False

    def open_folder(self, folder):
        if not self.server.folder_exists(folder):
            raise ValueError("Server reports that folder {} does not exist.".format(folder))
        response = self.server.select_folder(folder)
        self.current_folder = folder        

    def get_all_uids(self):
        return self.server.search()
        
    def fetch(self, mail_uids):
        '''Thin wrapper around IMAPClient's fetch method; fetches full message, date, and flags.
        Returns a UID-indexed dict where each UID refers to a dict
        with keys "email", "time", "flags".
        Email is the raw email body, time is a native timezone-aware datetime object,
        flags is a tuple of flags.
        Can be called either on a single (string) UID or a list of (string) UIDs.
        '''
        if isinstance(mail_uids, str):
            mail_uids = [mail_uids]
        elif not isinstance(mail_uids, list):
            raise TypeError("mail_uids must be either a single (string) UID or a list of UIDs.")
        mail_data = self.server.fetch(mail_uids, ["RFC822","INTERNALDATE","FLAGS"])
        mail_data2 = {}
        for UID, mail_dict in mail_data.items():
            mail_data2[UID] = { "email": mail_dict['RFC822'],
                                "time": mail_dict['INTERNALDATE'],
                                "flags": mail_dict['FLAGS'],
                                "folder": self.current_folder }
        return mail_data2

    def append(self, email, time, flags, folder='INBOX'):
        '''Thin wrapper around IMAPClient's append.
        Expects args 'email','time','flags', and 'folder', which are conveniently
        the same as the keys returned by the fetch method, allowing double-star
        assignment directly to this method.'''
        if not self.server.folder_exists(folder):
            self.server.create_folder(folder)
        self.server.append(folder, email, flags, time)

class _DummyMbox:
    # For convenience only; is instantiated instead of a real mbox if no local
    # copy is desired.
    def lock(self, *args, **kwargs):    pass
    def add(self, *args, **kwargs):     pass
    def unlock(self, *args, **kwargs):  pass
    def flush(self, *args, **kwargs):   pass
    def close(self, *args, **kwargs):   pass

# MSN etc not possible: Microsoft don't support IMAP.
providers = {"gmail":{"host":'imap.gmail.com', "port": 993},
             "yahoo":{"host":'imap.mail.yahoo.com', "port":993}
             }

# Arguments!
argp = argparse.ArgumentParser(
    description = ("A tool to help backup mail from some commonly used US servers prior to account deletion."
    " Uses the IMAP protocol to retreive messages from server and save to an mbox file."),
    epilog="by Cathal Garvey. Licensed under the GNU Affero General Public License v3 or later.")

argp.add_argument("-su","--source-username",
                        help = "Username of account to transfer from.")
argp.add_argument("-sP","--source-password",
                        help = "Password of account to transfer from. Will be prompted for if not given.")
argp.add_argument("-sh","--source-host", default = "imap.gmail.com",
                        help = "Host address, default 'imap.gmail.com'.")
argp.add_argument("-sp","--source-port", type = int, default = 993,
                        help = "Host port, default '993'.")
argp.add_argument("-s","--ssl", type = bool, default = True,
                        help = "Use ssl. Default is 'True'. Set 'False' if unwanted.")
argp.add_argument("-f","--folder", default = "inbox",
                        help = "Folder to copy. Default is 'inbox'. If not already on destination, it will be created.")
args = argp.parse_args()

for a in ['source_username']:
    if not getattr(args, a, False):
        print("""\
Error: Must specify the following arguments at least:
--source-host , --source-username, --dest-host, --dest-username,
Try calling with --help for further information on these and other arguments.""")
        sys.exit(1)

# Get password securely.
if not getattr(args, "source_password", False):
    p = getpass.getpass("Please provide password for remote server:".format(a))
    setattr(args, "source_password", p)
    print("Password was:",args.source_password) # Debug only! Defeats the point of using getpass! :)

# Create "from" account object.
# DumbMailClient(self, host, port, username, password, ssl = True):
FromAccount = DumbMailClient( args.source_host, args.source_port,
                              args.source_username, args.source_password,
                              ssl = args.ssl)
FromAccount.open_folder(args.folder)

local_mailbox_name = "{0}:{1}:{2}".format(args.source_username, args.source_host, args.folder)
local_mailbox_mapping = local_mailbox_name + "-uid_mapping.json"
local_mailbox = mailbox.mbox(local_mailbox_name+".mbox")
local_mailbox.lock()

# Mapping file maps remote UIDs to local UIDs, as these will be different.
# Remote UIDs are not critical unless cross-server operations will be needed,
# perhaps to verify successful download of various messages prior to deletion.
if os.path.exists(local_mailbox_mapping):
    with open(local_mailbox_mapping) as InF:
        local_mapping = json.load(InF)
else:
    local_mapping = {}

def save_mapping():
    with open(local_mailbox_mapping,"w") as OutF:
        json.dump(local_mapping, OutF)

msgcount = 0
allmsgs = _uniquify(FromAccount.get_all_uids())
msgnum = len(allmsgs)
print("Server reports {0} messages.".format(msgnum))
for message_block in _chunks(allmsgs, 10):
    try:
        skipped = 0
        for m_uid in message_block:
            if m_uid in local_mapping:
                message_block.remove(m_uid)
                skipped += 1
        messages = FromAccount.fetch(message_block)
        for m_uid, m in messages.items():
            # Adds mail to remote account.
            if m_uid not in local_mapping:
                # Add to local mbox and get uid, or don't and store "None".
                local_key = local_mailbox.add(m['email'])
                # Save mapping of original uid to mbox key, may be valuable later when
                # verifying possession of mails on source server, and local mapping
                # is thus a record of which emails have already been "done".
                local_mapping[m_uid] = local_key
                msgcount += 1
            else: 
                skipped += 1
        # Flush local mbox for this block of 10 messages.
        print("Saving messages up to {0}/{1}, skipping {2} previously saved.".format(msgcount, msgnum, skipped))
        local_mailbox.flush()
        save_mapping()
    except KeyboardInterrupt: # Remarkably easy to do this by mistake for long operations.
        reallyquit = input("Do you really want to cancel backing up? (y/N) ")
        if reallyquit.lower()[0] == "y": break
        else: pass

local_mailbox.close()

if args.local:
    print("Saving key mapping of mail UIDs to local mbox keys..")
    save_mapping()
print("Finished!")
