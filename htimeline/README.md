# Extract Tool

Tool to extract smaller Horovod timelines from a large timeline. 

On the first run, saves timeline metadata and index to file.

Note: ujson module is not required, but is highly recommended. Speedup is ~2x

## Modes

* `--extract`
    * Create a shorter timeline file. 
    * Required arguments: `--start_time` and `--duration `
    * Will regenerate timeline metadata if required
* `--stats` 
    * Reads current metadata (file size, timeline duration, etc.)
    * May be out of date if timeline is live and metadata was generated previously.
    * Can use `--live` flag to force metadata rebuild if timeline file has grown since last metadata build


## Examples
`python extract.py --extract --timeline ../gitignored/large_htimeline.json --start_time 0 --duration 20`

`python extract.py --stats --timeline ../gitignored/large_htimeline.json`

`python extract.py --stats --live --timeline ../gitignored/large_htimeline.json`

