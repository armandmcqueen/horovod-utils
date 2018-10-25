#!/usr/bin/env bash

INTERFACE=${1:-ens3}
while sleep .001; do printf '%s %s\n' "$(date '+%s%3N')" "$(ethtool -S ${INTERFACE} | grep 'rx_bytes\|tx_bytes' | xargs)"; done >> network_buffer_log.txt