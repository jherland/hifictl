#!/bin/sh

socat -d -d -v pty,rawer,echo=0,link=./reader pty,rawer,echo=0,link=./writer
