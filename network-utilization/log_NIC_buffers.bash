#!/usr/bin/env bash

while sleep .001; do printf '%s %s\n' "$(date '+%s%3N')" "$(ethtool -S ens3 | grep 'rx_bytes\|tx_bytes' | xargs)"; done >> network_buffer_log.txt