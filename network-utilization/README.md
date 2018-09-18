# NU

Record and Graph High-Granularity Network Throughput


##### Record network usage for next 60 seconds and SimpleSample that data
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