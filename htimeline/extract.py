#!/usr/bin/env python3

import os
import io
from os.path import abspath
import itertools, sys
import time
import argparse

spinner = itertools.cycle(['\\', '|', '/', '-'])
MICROSECONDS_PER_SEC = 1000 * 1000.
BYTES_PER_KB = 1000.
BYTES_PER_MB = 1000 * 1000.
BYTES_PER_GB = 1000 * 1000 * 1000.
BYTES_PER_TB = 1000 * 1000 * 1000 * 1000.
BYTES_PER_PB = 1000 * 1000 * 1000 * 1000 * 1000.

try:
    import ujson as json
except ImportError:
    print("#########################################################################################################")
    print("WARNING: ujson module is unavailable. Falling back to json module. ujson would be roughly twice as fast")
    print("#########################################################################################################")
    import json


try:
    from tqdm import tqdm
except ImportError:
    print("tqdm module is unavailable")
    class tqdm:
        def __init__(self, total):
            self.total = float(total)
            self.at = 0
            self.last_time = time.time()
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

        def update(self, step):
            MIN_SPIN_STEP_TIME = 0.05   # Throttle the spinne4

            self.at += step
            percent = self.at/self.total

            t = time.time()

            elapsed_seconds = t - self.last_time
            if elapsed_seconds < MIN_SPIN_STEP_TIME:
                return
            self.last_time = t
            self.update_spinner(percent)


        def update_spinner(self, percent):

            percent_2dec = f'{"%.2f" % (percent*100)}'
            if percent != 1.0:
                sys.stdout.write(f'{next(spinner)} {percent_2dec}%')
            else:
                sys.stdout.write(f'{percent_2dec}% ')

            sys.stdout.flush()  # flush stdout buffer (actual character display)
            backspaces = '\b\b' + ('\b'*len(percent_2dec)) + '\b' # [spinner][space] + [XX.XX] + [%]
            if percent != 1.0:
                sys.stdout.write(backspaces)

        def close(self):
            if not self.closed:
                self.closed = True
                if self.at != 1.0:
                    self.update_spinner(1.0)
                print("")




def print(s):
    sys.stdout.write(f'{s}\n')

def humanize(num):
    return "{:,}".format(num)

def humanize_float(num):
    return "{0:,.2f}".format(num)

def humanize_bytes(byte_count):
    if byte_count // 1000 == 0:
        return f'{humanize(byte_count)} bytes'
    elif byte_count // (1000 * 1000) == 0:
        return f'{humanize_float(byte_count / BYTES_PER_KB)} KB'
    elif byte_count // (1000 * 1000 * 1000) == 0:
        return f'{humanize_float(byte_count / BYTES_PER_MB)} MB'
    elif byte_count // (1000 * 1000 * 1000 * 1000) == 0:
        return f'{humanize_float(byte_count / BYTES_PER_GB)} GB'
    elif byte_count // (1000 * 1000 * 1000 * 1000 * 1000) == 0:
        return f'{humanize_float(byte_count / BYTES_PER_TB)} TB'
    else:
        return f'{humanize_float(byte_count / BYTES_PER_PB)} PB'



def blocks(files, size=65536):
    while True:
        b = files.read(size)
        if not b: break
        yield b
























class HorovodTimeline:

    def __init__(self, relpath, max_lines_to_scan_for_metadata=5 * 1000 * 1000, bytes_per_index=None, secs_per_index=1,
                 build_new_summary=False, max_extract_time=None, verbose=False, live=False):

        init_start_time = time.time()

        self.path = os.path.abspath(relpath)

        self.base_path = self.path.replace(".json", "") if self.path.endswith(".json") else self.path
        self.summary_json_path = self.base_path + ".sum.json"

        self.htimeline_size = os.path.getsize(self.path)

        self.min_ts = None
        self.max_ts = None
        self.duration_secs = None
        self.line_count = 0
        self.file_size_bytes = os.stat(self.path).st_size

        # What summaries need to be changed?
        build_new_line_count = False
        build_new_metadata = False
        build_new_index = False
        summary_json_has_changed = False

        print(f'LOADING HOROVOD TIMELINE')

        if os.path.exists(self.summary_json_path) and not build_new_summary:
            with open(self.summary_json_path, 'r') as summary_json_file:
                summary = json.load(summary_json_file)

                previous_file_size = summary["file_size"]
                self.line_count = summary["line_count"]
                self.min_ts = summary["min_ts"]
                self.max_ts = summary["max_ts"]
                self.duration_secs = (self.max_ts - self.min_ts) / MICROSECONDS_PER_SEC
                self.index = summary["index"]
                self.metadata_events = summary["metadata_events"]

                # lazily update summary
                if self.file_size_bytes != previous_file_size:

                    # Update if extract would include time not currently indexed
                    if max_extract_time:
                        max_extract_ms = max_extract_time * MICROSECONDS_PER_SEC
                        if max_extract_ms > self.max_ts:
                            build_new_line_count = True
                            build_new_index = True

                    # Update if --live flag is passed in and file has grown
                    if live:
                        build_new_line_count = True
                        build_new_index = True


        else:
            build_new_line_count = True
            build_new_metadata = True
            build_new_index = True

        if build_new_line_count:
            print("Scanning file for statistics")
            self.line_count, self.min_ts, self.max_ts = self.summarize(verbose=verbose)
            self.duration_secs = (self.max_ts - self.min_ts) / MICROSECONDS_PER_SEC
            summary_json_has_changed = True

        if build_new_metadata:
            print(f'Scanning first {humanize(max_lines_to_scan_for_metadata)} events for metadata events')
            self.metadata_events = self.find_metadata_events(max_lines_to_scan_for_metadata, verbose=verbose)
            summary_json_has_changed = True

        if build_new_index:
            print(f'Building index')
            if bytes_per_index is None:
                if secs_per_index is None:
                    raise RuntimeError("One of bytes_per_index or secs_per_index must be not None")
                jumps = self.duration_secs / secs_per_index
                bytes_per_index = int(self.file_size_bytes / jumps)

            self.index = self.build_index(bytes_per_index, verbose=verbose)
            summary_json_has_changed = True


        if summary_json_has_changed:
            with open(self.summary_json_path, 'w+') as summary_json_file:
                json.dump({
                    "line_count": self.line_count,
                    "min_ts": self.min_ts,
                    "max_ts": self.max_ts,
                    "index": self.index,
                    "metadata_events": self.metadata_events,
                    "file_size": self.file_size_bytes
                }, summary_json_file, indent=4)
        print("HOROVOD TIMELINE LOAD COMPLETE")
        init_end_time = time.time()

        if verbose:
            print("")
            print(f'Min ts: {humanize(self.min_ts)}')
            print(f'Max ts: {humanize(self.max_ts)}')
            if self.duration_secs > 120:
                print(f'Timeline Duration: {humanize_float(self.duration_secs/60)} mins / {humanize(int(self.duration_secs))} seconds')
            else:
                print(f'Timeline Duration: {humanize_float(self.duration_secs)} seconds')
            print(f'Time taken (Init new): {humanize_float(init_end_time - init_start_time)}s')

    def print_file_size(self):
        if self.file_size_bytes // 1000 == 0:
            print(f'File size: {humanize(self.file_size_bytes)} bytes')
        elif self.file_size_bytes // (1000 * 1000) == 0:
            print(f'File size: {humanize_float(self.file_size_bytes / BYTES_PER_KB)} KB')
        elif self.file_size_bytes // (1000 * 1000 * 1000) == 0:
            print(f'File size: {humanize_float(self.file_size_bytes / BYTES_PER_MB)} MB')
        elif self.file_size_bytes // (1000 * 1000 * 1000 * 1000) == 0:
            print(f'File size: {humanize_float(self.file_size_bytes / BYTES_PER_GB)} GB')
        elif self.file_size_bytes // (1000 * 1000 * 1000 * 1000 * 1000) == 0:
            print(f'File size: {humanize_float(self.file_size_bytes / BYTES_PER_TB)} TB')
        else:
            print(f'File size: GIGANTIC (PBs or larger)')

    def print_timeline_duration(self):
        if self.duration_secs > 120:
            print(f'Timeline Duration: {humanize_float(self.duration_secs/60)} mins')
        else:
            print(f'Timeline Duration: {humanize_float(self.duration_secs)} secs')

    def print_index_stats(self):
        diffs = []
        last_ts = None
        for ts, byte_ptr in self.index:
            if last_ts:
                diffs.append(ts - last_ts)
            last_ts = ts

        average_diff = sum(diffs) / float(len(diffs))

        print(f'{humanize(len(self.index))} indices built')
        # print(f'Average ts index gap is {humanize_float(average_diff)} microseconds')
        # print(f'Average ts index gap is {humanize_float(average_diff/1000.)}ms')
        print(f'Average time between indices is {humanize_float(average_diff/MICROSECONDS_PER_SEC)}s')

    def summarize(self, verbose=False):

        if verbose:
            self.print_file_size()
            print("")
            print(f'Finding min timestamp, max timestamp and counting lines')
            time.sleep(0.1)

        start_ts = time.time()
        with open(self.path, "r", encoding="utf-8", errors='ignore') as f:

            # MIN timestamp
            min_ts = None
            while min_ts is None:
                line = f.readline()
                ts = self.extract_ts_from_line(line, verbose=False)
                min_ts = ts

            # Line count
            f.seek(0)

            # lc = sum(bl.count("\n") for bl in blocks(f))

            with tqdm(total=self.file_size_bytes) as pbar:
                last = 0
                newlines = []
                for bl in blocks(f):
                    ptr = f.tell()
                    pbar.update(ptr - last)

                    newlines.append(bl.count("\n"))

                    last = ptr

            lc = sum(newlines)

            # MAX timestamp
            f.seek(self.file_size_bytes - (100 * 1000))
            f.readline()
            max_ts = 0
            for line in f:
                ts = self.extract_ts_from_line(line, verbose=False)
                if ts:
                    max_ts = max(ts, max_ts)

        end_ts = time.time()

        if verbose:
            time.sleep(0.1)
            print(f'Time taken (StackOverflow line count + min/max ts): {humanize_float(end_ts - start_ts)}s')
            self.print_timeline_duration()

        return lc, min_ts, max_ts



    def find_metadata_events(self, max_lines_to_scan, verbose=False):

        pbar_throttler = 10 * 1000
        pbar_count = 0
        results = []

        if verbose:
            print("")
            print(f'Scanning first {humanize(max_lines_to_scan)} lines for metadata events:')
        time.sleep(0.1)

        start_ts = time.time()
        with tqdm(total=max_lines_to_scan) as pbar:
            with open(self.path, 'r') as f:
                for line in f:
                    pbar_count += 1
                    if pbar_count % pbar_throttler == 0:
                        pbar.update(pbar_throttler)

                    j = self.parse_line_as_json(line, verbose=True)

                    if j and 'ts' not in j.keys():
                        results.append((pbar_count, line))

                    if pbar_count > max_lines_to_scan:
                        break

        end_ts = time.time()
        if verbose:
            time.sleep(0.1)
            print(f'Time taken (Find metadata): {"%.2f" % (end_ts - start_ts)}s')
        return [self.parse_line_as_json(result[1]) for result in results]


    def build_index(self, jump_bytes, verbose=False):

        # JUMP_ARG = 65536 # Default
        # JUMP_ARG = 32600

        def line_samples(files, jump=jump_bytes):
            max_jump = 65536 # For speed
            while True:

                if jump < max_jump:
                    b = files.read(jump)
                else:
                    jumped = 0
                    while jump-jumped > 0:
                        next_jump = min(jump-jumped, max_jump)
                        b=files.read(next_jump)
                        jumped += next_jump

                b = files.readline()
                b = files.readline()
                if not b: break
                yield b

        if verbose:
            print("")
            print(f'Building timestamp index:')
        time.sleep(0.1)

        start_ts = time.time()
        with tqdm(total=self.file_size_bytes) as pbar:
            last = 0
            with open(self.path, "r", encoding="utf-8", errors='ignore') as f:
                indices = []
                for sample_line in line_samples(f):
                    ptr = f.tell()
                    pbar.update(ptr - last)

                    ts = self.extract_ts_from_line(sample_line)
                    if ts:
                        indices.append((ts, ptr))

                    last = ptr

        end_ts = time.time()
        time.sleep(0.1)

        if verbose:
            self.print_index_stats()
            print(f'Time taken (TS index): {humanize_float(end_ts - start_ts)}s')
        return indices





    def print_stats(self, verbose=False):
        self.print_file_size()
        self.print_timeline_duration()
        print(f'{humanize(self.line_count)} lines in timeline file')
        self.print_index_stats()



    def parse_line_as_json(self, line, verbose=True):
        line = line.strip()
        if line[-2:] == "},":
            line = line[:-1]

        if line == "]" or line == "[":
            return None

        try:
            j = json.loads(line)
            return j
        except Exception as ex:
            if verbose:
                sys.stdout.write(str(ex))
                sys.stdout.write(f'[json.loads | ERROR]: "{line}"\n')
            return None

    def extract_ts_from_line(self, line, verbose=True):
        j = self.parse_line_as_json(line, verbose=verbose)
        if j is None:
            return None
        else:
            return j['ts'] if 'ts' in j.keys() else None

    def extract_ts_from_json(self, j):
        if j is None:
            return None
        else:
            return j['ts'] if 'ts' in j.keys() else None



    def extract_and_save_slice(self, start_secs, extract_duration_secs, return_slice=False, verbose=False):
        extract_file_path = f'{self.base_path}-extract-{start_secs}s-to-{start_secs+extract_duration_secs}s.json'
        if verbose:
            print(f'Extract file: {extract_file_path}')

        if return_slice:
            event_list = []
        min_extract_ts = start_secs*MICROSECONDS_PER_SEC + self.min_ts
        min_buffer_ts = min_extract_ts - (2*MICROSECONDS_PER_SEC)
        if min_buffer_ts < 0:
            min_buffer_ts = 0

        max_extract_ts = (start_secs+extract_duration_secs)*MICROSECONDS_PER_SEC + self.min_ts
        max_buffer_ts = max_extract_ts + (2*MICROSECONDS_PER_SEC)
        if max_buffer_ts > self.max_ts:
            max_buffer_ts = self.max_ts

        min_buffer_byte = self.search_index(min_buffer_ts)[0]
        max_buffer_byte = self.search_index(max_buffer_ts)[1]

        bytes_to_scan = max_buffer_byte - min_buffer_byte

        pbar_throttler = 10

        last_pbar_offset = 0

        i = 0

        print(f'Scanning {humanize_bytes(bytes_to_scan)}')
        time.sleep(0.1)
        with tqdm(total=bytes_to_scan) as pbar:
            with open(extract_file_path, 'w+') as o:
                o.write("[")
                first_line = True
                for metadata_event in self.metadata_events:
                    if first_line:
                        o.write(f'\n{json.dumps(metadata_event)}')
                        first_line = False
                    else:
                        o.write(f',\n{json.dumps(metadata_event)}')


                with open(self.path, 'r') as h:
                    h.seek(min_buffer_byte)
                    while True:
                        i += 1
                        if i % pbar_throttler == 0:
                            current_pbar_offset = h.tell() - min_buffer_byte
                            pbar.update(current_pbar_offset - last_pbar_offset)
                            last_pbar_offset = current_pbar_offset
                        line = h.readline()
                        j = self.parse_line_as_json(line, verbose=False)
                        ts = self.extract_ts_from_json(j)

                        if ts is not None:
                            if ts >= min_extract_ts and ts <= max_extract_ts:
                                if return_slice:
                                    event_list.append(j)
                                o.write(f',\n{json.dumps(j)}')


                        if h.tell() >= max_buffer_byte:
                            o.write("\n]")
                            if return_slice:
                                return extract_file_path, event_list
                            return extract_file_path, None



    # Returns (byte_index_before, byte_index_after)
    def search_index(self, find_ts):
        if find_ts <= self.min_ts:
            return (0, 0)

        if find_ts >= self.max_ts:
            return (self.file_size_bytes, self.file_size_bytes)

        last_ts = 0
        last_byte_index = 0
        for ts, byte_ind in self.index:
            # print(f'{humanize(ts)}    |   {humanize(byte_ind)}')
            if find_ts >= last_ts and find_ts <= ts:
                return (last_byte_index, byte_ind)

            last_ts = ts
            last_byte_index = byte_ind

        raise RuntimeError("Something went very wrong while scanning index")


    def confirm_index_is_valid(self):
        i = 0
        last_ts = 0
        last_byte_index = 0
        for ts, byte_ind in self.index:

            if ts < self.min_ts:
                return False, f'There is an index ts that is before the min_ts. Index ind {i}'

            if ts > self.max_ts:
                return False, f'There is an index ts that is asfter the max_ts. Index ind {i}'

            if last_ts > ts:
                return False, f'There is an out-of-order index. TS: {ts}, LastTS: {last_ts}. Index ind {i}'

            if last_byte_index > byte_ind:
                return False, f'There is an out-of-order byte_index. Index ind {i}'

            if byte_ind < 0:
                return False, f'There is a byte_index that is below 0. Index ind {i}'

            if byte_ind > self.file_size_bytes:
                return False, f'There is a byte_index greater than the file_size. Index ind {i}'

            last_ts = ts
            last_byte_index = byte_ind
            i += 1

        return True, "Index looks good"

    def examine_index(self, min_ind, max_ind):
        re = []
        for i in range(min_ind, max_ind+1):
            re.append(self.index[i])
        return re

















if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="HorovodTimelineUtils")

    parser.add_argument('--stats', help='Return statistics about the Horovod timeline (file size, duration, line count)', action="store_true")
    parser.add_argument('--extract', help='Extract a portion of the Horovod timeline', action="store_true")
    parser.add_argument('--verify_index', help='Verify that the index makes sense. Note: this does not verify that the index matches the timeline', action="store_true")

    parser.add_argument('--live', help='If file has grown since last metadata build, rebuild metadata', action="store_true")


    parser.add_argument('--timeline', type=str, help='Path to horovod_timeline. Required', required=True)
    parser.add_argument('--start_time', help='Start time in seconds. Can be decimal. Default=0', type=float, default=0.)
    parser.add_argument('--duration', help='Duration in seconds of timeline extract. Can be decimal. Default=10', type=float, default=10.)

    parser.add_argument('--verbose', help='Enable verbose mode. Currently poorly implemented. Dont use', type=bool, default=False)

    ARGS = parser.parse_args()

    # print(ARGS)
    print("")

    modes = [ARGS.stats, ARGS.extract, ARGS.verify_index]
    count_modes_chosen = sum([1 for m in modes if m])
    if count_modes_chosen > 1:
        raise RuntimeError(f'Only one of {str(modes)} may be chosen')
    if count_modes_chosen == 0:
        raise RuntimeError(f'One of {str(modes)} must be chosen')

    htimeline_path = abspath(ARGS.timeline)

    if ARGS.extract:
        end_time = ARGS.start_time + ARGS.duration

    else:
        end_time = None

    begin = time.time()
    h = HorovodTimeline(htimeline_path, max_extract_time=end_time, live=ARGS.live)


    print("")
    if ARGS.extract:

        print(f'Extracting {ARGS.start_time}s to {end_time}s from {ARGS.timeline}')
        print("")
        extract_file_name, _ = h.extract_and_save_slice(ARGS.start_time, ARGS.duration, verbose=ARGS.verbose)
        print("")
        print(f'Extract complete - {extract_file_name}')

    if ARGS.stats:
        print(f'Timeline Info:')
        print("")
        h.print_stats(verbose=ARGS.verbose)


    if ARGS.verify_index:
        print("Checking index is valid:")
        is_valid, mes = h.confirm_index_is_valid()
        print("")
        print(f'Index is {"valid" if is_valid else "invalid"}')
        if not is_valid:
            print(f'{mes}')





    end = time.time()

    if ARGS.verbose:
        time.sleep(0.1)
        print("")
        print(f'Total time taken = {humanize_float(end - begin)}s')

    print("")























