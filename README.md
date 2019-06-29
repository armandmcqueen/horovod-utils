# horovod-utils

Tools for working with Horovod

## htimeline

Command line tool for working with very large Horovod timeline files. Allows you to get a summary of the timeline (size, duration) and extract a slice of the timeline that will fit in memory for chrome://tracing

## Network Utilization

Utility for recording and graphing high-granularity network usage to determine if training is network bottlenecked. Functional, but TIG is now the recommended approach for examining network utilization.

## TIG

Utilities for installing the Telegraf-Influx-Grafana stack to monitor training performance.
