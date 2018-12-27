# Wrapper to generate telegraf config with more control

import argparse
import subprocess


def sh(cmd):
    subprocess.check_call(cmd, shell=True)



def generate_telegraf_conf(agent_interval, agent_flush_interval, influx_url, influx_db, tags, input_filters, hostname):
    sh("telegraf --input-filter "+input_filters+" --output-filter influxdb config > _telegraf.conf")

    with open('_telegraf.conf', 'r') as f:
        conf_lines = f.readlines()

    conf_lines = set_agent_interval(conf_lines, agent_interval)
    conf_lines = set_agent_flush_interval(conf_lines, agent_flush_interval)
    conf_lines = set_hostname(conf_lines, hostname)
    conf_lines = set_influxdb_urls(conf_lines, influx_url)
    conf_lines = set_influxdb_database(conf_lines, influx_db)

    for tag_pair in tags:
        split_tag_pair = tag_pair.split("=")
        if len(split_tag_pair) > 2:
            raise RuntimeError("Tag may have '=' in value. Input was: "+tag_pair)

        tag_name = split_tag_pair[0]
        tag_val = split_tag_pair[1]

        conf_lines = add_global_tag(conf_lines, tag_name, tag_val)

    with open('telegraf.conf', 'w+') as o:
        o.writelines(conf_lines)

    sh("rm _telegraf.conf")




def replace_param_line(conf_lines, confgroup_str, existing_param_string, new_param_string, keep_old_param_line=False):
    out_lines = []

    in_correct_confgroup = False
    for line in conf_lines:
        l = line.strip()
        if l == confgroup_str:
            in_correct_confgroup = True

        if in_correct_confgroup:
            if l == existing_param_string:
                if keep_old_param_line:
                    out_lines.append(line)
                line = line.replace(existing_param_string, new_param_string)

        out_lines.append(line)
    return out_lines


def set_agent_interval(conf_lines, new_interval):
    agent_group_str = '[agent]'
    existing_param_str = 'interval = "10s"'
    new_param_str = 'interval = "'+new_interval+'"'
    return replace_param_line(conf_lines, agent_group_str, existing_param_str, new_param_str)


def set_agent_flush_interval(conf_lines, new_interval):
    agent_group_str = '[agent]'
    existing_param_str = 'flush_interval = "10s"'
    new_param_str = 'flush_interval = "'+new_interval+'"'
    return replace_param_line(conf_lines, agent_group_str, existing_param_str, new_param_str)

def set_hostname(conf_lines, hostname):
    agent_group_str = '[agent]'
    existing_param_str = 'hostname = ""'
    new_param_str = 'hostname = "'+hostname+'"'
    return replace_param_line(conf_lines, agent_group_str, existing_param_str, new_param_str)

def set_influxdb_urls(conf_lines, new_url):
    influx_group_str = '[[outputs.influxdb]]'
    existing_param_str = '# urls = ["http://127.0.0.1:8086"]'
    new_param_str = 'urls = ["'+new_url+'"]'
    return replace_param_line(conf_lines, influx_group_str, existing_param_str, new_param_str)


def set_influxdb_database(conf_lines, new_database):
    influx_group_str = '[[outputs.influxdb]]'
    existing_param_str = '# database = "telegraf"'
    new_param_str = 'database = "'+new_database+'"'
    return replace_param_line(conf_lines, influx_group_str, existing_param_str, new_param_str)


def add_global_tag(conf_lines, tag_name, tag_val_str):
    global_tags_group_str = '[global_tags]'
    existing_param_str = '# user = "$USER"'
    new_param_str = tag_name + ' = "'+tag_val_str+'"'
    return replace_param_line(conf_lines, global_tags_group_str, existing_param_str, new_param_str, keep_old_param_line=True)


# Note, in generated telegraf.conf, the order of global tags will be the reverse of the order of the 'tags' param.
# If not accounted for, this will lead to incorrect test failures.
def test():
    print("Test starting...")

    agent_interval = '10ms'
    agent_flush_interval = '1s'
    influxdb_url = "http://127.0.0.1:8086"
    influxdb_db = "telegraf-test"
    tags = ["run=test-run", "cluster=armand-cluster-1"]
    input_filters = "cpu:mem:diskio:disk"
    hostname = "algo-1"

    generate_telegraf_conf(agent_interval, agent_flush_interval, influxdb_url, influxdb_db, tags, input_filters, hostname)

    with open('telegraf_example.conf', 'r') as gt:
        gt_lines = gt.readlines()

    with open('telegraf.conf', 'r') as actual:
        actual_lines = actual.readlines()

    for i, actual_line in enumerate(actual_lines):
        gt_line = gt_lines[i]
        # print("--")
        # print(gt_line)
        # print(actual_line)
        assert actual_line == gt_line

    sh("rm telegraf.conf")
    print("Test complete - SUCCESS")


if __name__ == "__main__":
    # test()

    parser = argparse.ArgumentParser(prog="telegraf-wrapper")

    parser.add_argument('--agent_interval', help='How often the agent extracts metrics, e.g. 10s, 10ms',
                                            default="1s")
    parser.add_argument('--agent_flush_interval', help='How often the agent flushes collected metrics, e.g. 10s, 10ms',
                                                  default="10s")
    parser.add_argument('--influx_url', help='The url and port of the influxdb instance, e.g. "http://127.0.0.1:8096"',
                                        default="http://127.0.0.1:8096")
    parser.add_argument('--influx_db', help='The name of the database to write metrics to. Will be created if doesnt exist. Default=telegraf',
                                       default='telegraf')
    parser.add_argument('--tags', help='Tag name=value pairs, e.g. "user=armand,cluster=2node-1,run=test-run". '
                                       'Allows you to filter in influxdb')
    parser.add_argument('--input_filters', help='Telegraf input sources to enabled as colon-seperated list. Default="cpu:mem:diskio:disk:nvidia_smi"',
                                            default="cpu:mem:diskio:disk:nvidia_smi")
    parser.add_argument('--test',
                        help='Run test to config telegraf_config.py is working',
                        action="store_true")
    parser.add_argument('--hostname',
                        help='Hostname. Default will use os.Hostname(). Default will not work correctly on SageMaker',
                        default='""')


    ARGS = parser.parse_args()

    if ARGS.test:
        test()
        quit()

    ARGS.tags = ARGS.tags.split(",")

    generate_telegraf_conf(ARGS.agent_interval,
                           ARGS.agent_flush_interval,
                           ARGS.influx_url,
                           ARGS.influx_db,
                           ARGS.tags,
                           ARGS.input_filters,
                           ARGS.hostname)






