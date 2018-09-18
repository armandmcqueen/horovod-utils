#!/usr/bin/env python3

import subprocess
import time
import contextlib
import platform
from multiprocessing import Process
import matplotlib.pyplot as plt
try:
    import ujson as json
except:
    print("Failed to import ujson. Unclear how much performance is impacted by ujson vs json modules")
    import json
import time
import os
import shutil
import argparse







class BufferTimeseries:
    def __init__(self, log_path=None, btfile_path=None):
        if log_path is None and btfile_path is None:
            raise RuntimeError("One of log_path or btfile_path must be specified")

        if log_path is not None and btfile_path is not None:
            raise RuntimeError("Only one of log_path or btfile_path may be specified")

        self.deltas_computed = False
        if log_path:
            self.timeseries = self.parse_raw_data(log_path)

        if btfile_path:
            with open(btfile_path, 'r') as btfile:
                self.timeseries = json.load(btfile)


    def __str__(self):
        return json.dumps(self.timeseries[:2], indent=4)

    def _timeseries(self):
        # For debugging
        return self.timeseries


    # line = "1536614209799 queue_0_tx_bytes: 329065983972 queue_0_rx_bytes: 586750605557 queue_1_tx_bytes: 17063270918 ..."
    # return (ts, kv_pair_tuple_list):
    # = int(1536614209799), [("queue_0_tx_bytes", int(329065983972), ("queue_0_rx_bytes", int(586750605557), ...]
    def parse_line(self, line):
        split_line = line.replace(": ", ":").replace("\n", "").strip().split(" ")
        ts = int(split_line[0])
        kv_pairs_str = split_line[1:]

        kv_pairs = []
        for kv in kv_pairs_str:
            k, v = kv.split(":")
            kv_pairs.append((k, int(v)))
        return ts, kv_pairs


    def parse_raw_data(self, raw_data_path):
        start = time.time()
        with open(raw_data_path, 'r') as raw_data:
            timeseries = []
            for line in raw_data:
                snapshot = {}
                ts, queue_kv_pairs = self.parse_line(line)
                snapshot['raw'] = {'timestamp': ts,
                                   'queues': {}}
                for k ,v in queue_kv_pairs:                     # e.g. k,v = ("queue_0_tx_bytes", int(329065983972))
                    try:
                        _, q_num, rxtx, _ = k.split("_")
                        q_id = f'{rxtx}_{q_num}'  # e.g: 'tx_0'

                        snapshot['raw']['queues'][q_id] = v

                    except Exception as ex:
                        print("error")
                        print(k, v)
                        print(ex)

                timeseries.append(snapshot)
        end = time.time()
        print(f'Parsed log file in {end - start}s')
        return timeseries



    def add_computed_layers(self):
        start = time.time()
        if self.deltas_computed:
            return
        
        for i, snapshot in enumerate(self.timeseries):
            if i == 0:
                prev_snapshot = snapshot
                continue


            ##################################################################
            ####    Deltas
            ##################################################################
            ts = snapshot['raw']['timestamp']
            prev_ts = prev_snapshot['raw']['timestamp']
            ts_delta = ts - prev_ts

            snapshot['deltas'] = {
                "timestamp": ts_delta,
                "queues": {}
            }


            
            for q_id in snapshot['raw']['queues'].keys():
                current_bytes = snapshot['raw']['queues'][q_id]
                prev_bytes = prev_snapshot['raw']['queues'][q_id]

                delta_bytes = current_bytes - prev_bytes
                snapshot['deltas']['queues'][q_id] = delta_bytes

            ##################################################################
            ####    Gigabit/s Projection
            ##################################################################
            def to_gigabits_per_sec(ms_delta, byte_delta):
                bits = byte_delta * 8
                bits_per_ms = bits / ms_delta
                gigabits_per_ms = bits_per_ms / (1000 * 1000 * 1000)
                gigabits_per_sec = gigabits_per_ms * 1000
                return gigabits_per_sec

            snapshot['gbps'] = {
                "rx": 0,
                "tx": 0
            }
            for q_id in snapshot['raw']['queues'].keys():
                gbps = to_gigabits_per_sec(snapshot['deltas']['timestamp'], snapshot['deltas']['queues'][q_id])
                if q_id.startswith('tx'):
                    snapshot['gbps']['tx'] += gbps
                elif q_id.startswith('rx'):
                    snapshot['gbps']['rx'] += gbps
                else:
                    raise RuntimeError(f'Unrecognized queue id: {q_id}')

            prev_snapshot = snapshot

        self.deltas_computed = True
        end = time.time()
        print(f'Adding computed layers complete: {end-start}s')


    def extract(self, start_ms=None, duration_ms=None, reduce_to_min_state=False):
        start_raw_ms = self.timeseries[0]['raw']['timestamp']
        end_raw_ms = self.timeseries[-1]['raw']['timestamp']

        if start_ms is not None:
            start_raw_ms += start_ms

        if duration_ms is not None:
            end_raw_ms = start_raw_ms + duration_ms

        extract_timeseries = []
        for snapshot in self.timeseries:
            if snapshot['raw']['timestamp'] < start_raw_ms:
                continue

            if snapshot['raw']['timestamp'] > end_raw_ms:
                break

            if reduce_to_min_state:
                extract_snapshot = {'raw': snapshot['raw']}
            else:
                extract_snapshot = snapshot

            extract_timeseries.append(extract_snapshot)
        return extract_timeseries

    def reduce(self, start_ms=None, duration_ms=None):
        self.timeseries = self.extract(start_ms=start_ms, duration_ms=duration_ms)
        return None # changes state, doesn't return


    def graph_network_usage(self, title=None, skip_ms=0, length_ms=None, save_path=None, plt_shot=False):
        if not self.deltas_computed:
            self.add_computed_layers()

        reduced_timeseries = self.extract(start_ms=skip_ms, duration_ms=length_ms)
        rx_timeseries = []
        tx_timeseries = []
        ts_timeseries = []
        for i, snapshot in enumerate(reduced_timeseries):
            if i == 0: # The first snapshot might not have gbps
                if 'gbps' not in snapshot:
                    continue

            rx_timeseries.append(snapshot['gbps']['rx'])
            tx_timeseries.append(snapshot['gbps']['tx'])
            ts_timeseries.append(snapshot['raw']['timestamp'])


        t0 = ts_timeseries[0]
        # Shift so t0 = 0 and convert to seconds
        ts_timeseries = [(t-t0)/1000 for t in ts_timeseries]

        if len(rx_timeseries) != len(tx_timeseries):
            raise RuntimeError("Code expects rx and tx timeseries to be of the same length")


        fig, (ax1, ax2) = plt.subplots(nrows=2)
        ax1.plot(ts_timeseries, rx_timeseries, '-b', label="Received")
        ax2.plot(ts_timeseries, tx_timeseries, '-r', label="Transmitted)")

        ax1.set_ylabel("Gbit/s")
        # ax1.set_xlabel("Time (seconds)")

        ax2.set_ylabel("Gbit/s")
        ax2.set_xlabel("Time (seconds)")

        ax1.legend(loc=1)
        ax2.legend(loc=1)

        if title is not None:
            ax1.set_title(title)

        if save_path is not None:
            plt.savefig(save_path)
            plt.close()

        if plt_shot:
            plt.show()

        return plt


    
    
    
    


    def save(self, save_path, start_ms=None, duration_ms=None):
        with open(save_path, 'w+') as out:
            json.dump(self.extract(start_ms=start_ms, duration_ms=duration_ms, reduce_to_min_state=True), out)

    def simple_sampler(self, dir_path=None, start=None, sample_sizes=(60, 10, 5, 2, 1, 0.5, 0.1)):

        if dir_path == None:
            dir_path = os.getcwd()
            simple_sample_dir_path = os.path.join(dir_path, "SimpleSample")
            if not os.path.isdir(simple_sample_dir_path):
                os.mkdir(simple_sample_dir_path)
            dir_path = simple_sample_dir_path

        if start is None:
            start = 0

        _ = self.graph_network_usage(title=f'Complete Sample', save_path=os.path.join(dir_path, 'complete_sample.png'))

        self.reduce(start_ms=start, duration_ms=60*1000)


        for sample_dur_secs in sample_sizes:
            filename = f'{sample_dur_secs}_second_sample.png'
            p = os.path.join(dir_path, filename)
            _ = bt.graph_network_usage(title=f'{sample_dur_secs} Second Sample', length_ms=sample_dur_secs*1000, save_path=p)

        self.save(save_path=os.path.join(dir_path, 'sample_data.bt.json'))



def to_ms(dur_str):
    try:
        if dur_str.endswith('ms'):
            return float(dur_str[:-2])
        if dur_str.endswith('s'):
            return float(dur_str[:-1]) * 1000
        if dur_str.endswith('m'):
            return float(dur_str[:-1]) * 60 * 1000
        else:
            # Assume seconds
            return float(dur_str) * 1000
    except Exception as ex:
        print(f'Failed to convert "{dur_str}" to ms')
        print(ex)

# Convert path string to absolute path.
def abspathify(path_str):
    if path_str.startswith("/"):
        return path_str
    elif path_str.startswith("~"):
        return os.path.abspath(path_str)
    else:
        return os.path.abspath(os.path.join(os.getcwd(), path_str))


def record_network_buffer_log(save_dir):
    if platform.system() != "Linux":
        raise RuntimeError("--live requires ethtool and is only supported on Linux")
    save_filepath = os.path.join(save_dir, 'network_buffer_log.txt')
    with contextlib.suppress(FileNotFoundError):
        os.remove(save_filepath)
    cmd = "while sleep .001; do printf '%s %s\n' \"$(date '+%s%3N')\" \"$(ethtool -S ens3 | grep 'rx_bytes\|tx_bytes' | xargs)\"; done >> " + save_filepath
    subprocess.check_output(cmd, shell=True)




if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog="HighGranularityNetworkUtilization")

    # Primary arguments
    parser.add_argument('--simplesample', help='Extracts and graphs default slices of network logs. Good starting place', action="store_true")
    parser.add_argument('--extract', help='Extract and save a subset of the network logs', action="store_true")
    parser.add_argument('--graph', help='Generate a graph of the network logs. Save graph as image with --save', action="store_true")


    parser.add_argument('--raw', help='Path to raw network logs', type=str)
    parser.add_argument('--saved', help='Path to saved parsed network logs. If value does not end in ".json", will automatically add ".bt.json"', type=str)
    parser.add_argument('--live', help='[--simplesample] Use live network data instead of previously collected data', action="store_true")

    parser.add_argument('--start', help='Start time of extract or graph (offset from first log entry timestamp). Examples: "10s", "1m", "500ms". Without unit, the value is assumed to be seconds', type=str)
    parser.add_argument('--duration', help='Duration of extract or graph. Examples: "10s", "1m", "500ms". Without unit, the value is assumed to be seconds', type=str)

    parser.add_argument('--save', help='[--graph] Save the graph as an image instead of displaying. Value is path to image file, e.g. "my_graph.png"\n[--extract] Extract name, e.g."network_util_2_node_60s_to_180s.bt.json" or "network_util_2_node_60s_to_180s" (".bt.json" part is optional). "network_util_2_node_60s_to_180s.json" is allowed, but not recommended', type=str)
    parser.add_argument('--simplesamplesave', help='[--simplesample only] Folder to save SimpleSample output to. Will create a SimpleSample folder within dir. Default is current working directory', type=str)
    parser.add_argument('--title', help='Title for graph', type=str)

    parser.add_argument('--verbose', help='Enable verbose mode', action="store_true")

    ARGS = parser.parse_args()


    ##############################################
    ### Only allow one primary argument
    ##############################################
    primary_options = ['simplesample', 'extract', 'graph']
    active_primary_options = [prim_opt for prim_opt in primary_options if ARGS.__dict__[prim_opt]]

    if len(active_primary_options) != 1:
        raise RuntimeError(f'Exactly one primary option must be set. Primary options are {primary_options}. Currently, {active_primary_options if len(active_primary_options) > 0 else "none"} are set')


    ##############################################
    ### Parse START and DURATION params
    ##############################################
    start_ms = to_ms(ARGS.start) if ARGS.start else 0
    duration_ms = to_ms(ARGS.duration) if ARGS.duration else None


    ##############################################
    ### Parse SAVED and RAW input params
    ##############################################
    if ARGS.raw:
        ARGS.raw = abspathify(ARGS.raw)
    else:
        ARGS.raw = None

    if ARGS.saved:
        if not ARGS.saved.endswith(".json"):
            ARGS.saved += ".bt.json"

        ARGS.saved = abspathify(ARGS.saved)
    else:
        ARGS.saved = None




    ##############################################
    # --simple-sample
    ##############################################

    if ARGS.simplesample:
        # Set up dir to save output
        if not ARGS.save:
            ARGS.save = os.getcwd()
        ARGS.save = abspathify(ARGS.save)
        ARGS.save = os.path.join(ARGS.save, 'SimpleSample')

        shutil.rmtree(ARGS.save, ignore_errors=True)
        os.makedirs(ARGS.save)

        # Create raw buffer logs if needed
        if ARGS.live:
            if platform.system() != "Linux":
                raise RuntimeError("--live requires ethtool and is only supported on Linux")
            print("Recording network logs for next 60 seconds")
            recording_proc = Process(target=record_network_buffer_log, args=[ARGS.save])
            recording_proc.start()
            time.sleep(60)
            recording_proc.terminate()
            print("Recording complete")

            ARGS.raw = os.path.join(ARGS.save, "network_buffer_log.txt")
            start_ms = 0

        bt = BufferTimeseries(log_path=ARGS.raw, btfile_path=ARGS.saved)
        bt.simple_sampler(ARGS.save, start=start_ms)



    ##############################################
    # --extract
    ##############################################
    if ARGS.extract:
        if ARGS.save is None:
            raise RuntimeError("--save must be specified for an extraction")

        if not ARGS.save.endswith("json"):
            ARGS.save += ".bt.json"
        ARGS.save = abspathify(ARGS.save)

        bt = BufferTimeseries(log_path=ARGS.raw, btfile_path=ARGS.saved)
        bt.save(ARGS.save, start_ms=start_ms, duration_ms=duration_ms)



    ##############################################
    # --graph
    ##############################################
    if ARGS.graph:
        if ARGS.save:
            ARGS.save = abspathify(ARGS.save)
        show_graph = False if ARGS.save else True
        graph_title = ARGS.title if ARGS.title else "Network Utilization"

        bt = BufferTimeseries(log_path=ARGS.raw, btfile_path=ARGS.saved)
        bt.graph_network_usage(title=graph_title, skip_ms=start_ms, length_ms=duration_ms, save_path=ARGS.save,
                               plt_shot=show_graph)










