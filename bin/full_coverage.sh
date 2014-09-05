#!/bin/bash

set +e
export INBOX_ENV=test

pids=()

color() {
      printf '\033[%sm%s\033[m\n' "$@"
      # usage color "31;5" "string"
      # 0 default
      # 5 blink, 1 strong, 4 underlined
      # fg: 31 red,  32 green, 33 yellow, 34 blue, 35 purple, 36 cyan, 37 white
      # bg: 40 black, 41 red, 44 blue, 45 purple
}

colorn() {
      printf '\033[%sm%s\033[m' "$@"
      # color without a newline
}

run_for_cover()
{
    colorn '32;1' "running:  "
    color '36;1' $1
    coverage run --source /vagrant/inbox -p bin/$1 $2 > /tmp/$1.out 2> /tmp/$1.err  &
    pids+=("$!")
}

# Start the services
run_for_cover inbox-start
sleep 4
run_for_cover inbox-api --prod

# Run the system tests
py.test tests/system/test_sending.py --tb=short -s

kill -15 ${pids[@]}
wait ${pids[@]}
coverage combine
coverage html
cwd=`pwd`
color '32;1' "finished!"
