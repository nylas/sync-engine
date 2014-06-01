#!/bin/sh
# Run unit tests in a VM, and land change only if they pass.

current_branch=$(git symbolic-ref --short -q HEAD)
if [ "master" != "$current_branch" ]; then
    # Can only run this if not on master
    arc land --hold
fi

vagrant up
if vagrant ssh -c 'cd /vagrant; ./runtests'; then
    echo 'Unit test passed; landing change'
    arc amend && git push
else
    echo 'Unit test failures; aborting'
fi
