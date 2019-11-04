#!/bin/bash

mydir=$(dirname "$0")

PDU_HOSTNAME=192.168.234.115
MIBDIR=$mydir
MIB=PowerNet-MIB
OUTLET_PREFIX=$MIB::sPDUOutletCtl.
STATE_STRING=$MIB::sPDUMasterState.0

TURN_ON=1
TURN_OFF=2
REBOOT=3

outlet=$1
action=$2

if [ "$action" = "on" ]; then
    action=$TURN_ON
elif [ "$action" = "off" ]; then
    action=$TURN_OFF
elif [ "$action" = "reboot" ]; then
    action=$REBOOT
fi

args=("-m$MIB" "-M-$MIBDIR" -v1 -cprivate "$PDU_HOSTNAME")

if [ -z "$outlet" ]; then
    exec snmpget "${args[@]}" "$STATE_STRING"
elif [ "$outlet" = "walk" ]; then
    # Drop 'enterprise' for a different list
    exec snmpwalk "${args[@]}" enterprise
fi

if [ -z "$action" ]; then
    exec snmpget "${args[@]}" "$OUTLET_PREFIX$outlet"
fi

exec snmpset "${args[@]}" "$OUTLET_PREFIX$outlet" i "$action"
