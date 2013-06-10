# Refugeemail
by Cathal Garvey
Licensed under the GNU Affero General Public License, v3 or greater.

## What is this?
This is a pair of Python scripts designed to assist in ditching US servers and regaining some measure of your personal privacy.

These scripts use the IMAP protocol to fetch all mail (not necessarily in order) from the source server, saves all mail locally to an mBox file (unless directed not to keep local copies with "--local False"), and uses IMAP to place the emails on another remote server. The refugeemail_local_only.py script *only* saves mail locally to an mBox file.

Besides the mBox file, there is also a "username@domain:folder.uid-mapping.json" file, which keeps track of which mails have been successfully saved or transferred. Mild false-negatives may occur if the script is interrupted and restarted, wherein the script will copy/transfer mails twice, but false positives should not occur. Do not delete this file until all emails have been successfully saved or transferred!

## Why?
I moved my email address to an Icelandic server months ago, after a long process of preparation. I was inspired to seek more respectful shores for my data when I became a subject of suspicion because of a hobby. That sums up why you, too, should move: when doing anything but working 9-5 and watching TV all night makes you an object of suspicion, you're living in a totalitarian dystopia. Do something about it.

## How?
After installing Python 3, open a terminal/command prompt, navigate to the folder where these scripts are, and call using "python3 refugeemail.py --help" to get a list of options.

The default server settings are for Gmail, so Gmail "users" can just type: "python3 refugeemail.py -sU "myusername@gmail.com" -dU "myaccount@destinationdomain.com" -dh "destinationdomain.com" -dp 993

You can either pass your password for source and destination servers using "-sP" and "-dP", or you will be prompted for them.

Transfers are done in batches of 10 to reduce issues with script failure. The process is verbose, so you can see your progress as it runs.
