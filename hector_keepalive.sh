#!/bin/bash

# Script for restarting Hector automatically on failure.

TEST_SERVER="discordapp.com"
PYTHON_EXEC=python3.7
HECTOR_DIR=

while 1;do
	ping -c 1 $TEST_SERVER -w 5 # test for connection to discord
	if [ $? -eq 0 ];then
		$PYTHON_EXEC $HECTOR_DIR/hector.py
	fi
	sleep 10s # Wait at least 10 seconds between connection attempts
done
