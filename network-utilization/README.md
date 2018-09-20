# NU

Record and Graph High-Granularity Network Throughput

## Modes

* `--extract`
    * Parse and extract a slice of the buffer logs. Can take as input either a saved BufferTimeline extract or the raw log file 
    * Use `--raw` to sample from a saved network_buffer_log.txt
    * Use `--saved` to sample from a saved BufferTimeline extract. Can skip the '.bt.json' of the filename
    * `--start` is the start time of the extract. Measured as time from first log event. Can specify seconds, minutes or milliseconds Default is seconds. 
        * e.g. 5s, 10ms, 1m, 10 (= 10s)
    * `--duration` to specify the length of the extract. Same time notation as `--start`
* `--graph`
    * Generate a graph of the network usage from either raw data or saved BufferTimeline extract
    * `--start` and `--duration` is the same as above
    * `--save` to save the graph as an image. If `--save` is not specified, graph is displayed. Otherwise it is not.
    * '--title' to specify a title for the graph
    
* `--simplesample`
    * Take network log data and generate several graphs, using common slice durations
    * Good starting place
    * Use `--raw` to sample from a saved network_buffer_log.txt
    * Use `--saved` to sample from a saved BufferTimeline extract. Can skip the '.bt.json' of the filename
    * Use `--live` to generate a new network_buffer_log.txt from the next minute of network activity. Linux only
    * `--save` to specify the base folder to save the output to. SimpleSample will always create a SimpleSample folder within the base folder.
    * `--start` is a time offset to begin the sample. Default is first log line.
    

## Examples
##### Record network usage for next 60 seconds and SimpleSample that data
`./nu.py --simplesample --live`

##### Same as above, but specify where to put output
`./nu.py --simplesample --live --save ../gitignored/from_live`

##### Extract and save a slice of the network logs (60s to 150s)
`./nu.py --extract --raw ../gitignored/network_buffer_log.txt --start 1m --duration 90s --save ../gitignored/test_BufferTimeline_extract_60s_to_150s`

##### Run SimpleSample on raw data
`./nu.py --simplesample --raw ../gitignored/network_buffer_log.txt --save ../gitignored/from_raw`

##### Run SimpleSample on saved extract
`./nu.py --simplesample --saved ../gitignored/test_BufferTimeline_extract_60s_to_150s --save ../gitignored/from_extract`

##### Graph a 1500ms slice of the raw data. Display the graph
`./nu.py --graph --raw ../gitignored/network_buffer_log.txt --title "Test Title (60s to 61.5s)" --start 1m --duration 1500ms`

##### Graph a 500ms slice of the saved extract and save the graph as a PNG. Do not display the graph
`./nu.py --graph --saved ../gitignored/test_BufferTimeline_extract_60s_to_150s --title "Test Title (30s to 30.5s)" --start 30s --duration 500ms --save ../gitignored/from_extract/test_graph.png`

#### Time Denominations
* Mins (m)
* Secs (s)
* Milliseconds (ms)