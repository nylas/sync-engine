#!/bin/bash

# Get user's email address
read -e -a email_address -p "Enter the email account to sync and press [enter]: "

# Start sync server if need be
if pidof -x "inbox" >/dev/null; then
    	echo ""
    else
    	./inbox start &
fi

# Auth account, start sync
./inbox add $email_address

python run.py