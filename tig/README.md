# TIG Stack

- Telegraf
- InfluxDB
- Grafana

## Tooling

The TIG stack makes it easier to optimize distributed training by gathering and presenting metrics to help identify bottlenecks. This repo contains tooling to make setting up and using the TIG stack trivial. 

## Goal

Manually handle InfluxDB and Grafana

Automatically generate and run telegraf with a single command. Allow user to set configuration via cli - agent interval, flush interval, global tags (for multi-tenancy of influx), influx ip

Telegraf gives limited options when generating configuration. Add wrapper to add more options, intelligent defaults and automatic launching in background: 

`telegraf --input-filter cpu:mem:diskio:disk:nvidia_smi --output-filter influxdb config > telegraf.conf`


## Command Line Arguments


```
python telegraf_config.py \
    --agent_interval 1s \
    --agent_flush_interval 10s \
    --influx_url http://127.0.0.1:8096 \
    --influx_db telegraf \
    --tags user=armand,cluster=2node-vgg,run=test-run \
    --input_filters cpu:mem:diskio:disk:nvidia_smi 
```


## Setup

You should create a centralized instance that runs influxdb and grafana. 

On Amazon Linux, these are the steps to setup:

### Download influx binary

https://portal.influxdata.com/downloads

wget https://dl.influxdata.com/influxdb/releases/influxdb-1.7.2.x86_64.rpm
sudo yum localinstall influxdb-1.7.2.x86_64.rpm

#### Start influx
sudo service influxdb start

### Download grafana 

wget https://dl.grafana.com/oss/release/grafana-5.4.2-1.x86_64.rpm 
sudo yum localinstall grafana-5.4.2-1.x86_64.rpm 

#### Start grafana
sudo service grafana-server start

#### Expose grafana
We currently do not want to expose grafana to the world. Instead, use SSH to reroute grafana's web ui at port 3000 to localhost:3000

ssh -L 127.0.0.1:3000:127.0.0.1:3000 ec2-user@35.172.223.128

### Install Telegraf

#### Amazon Linux
wget https://dl.influxdata.com/telegraf/releases/telegraf-1.9.1-1.x86_64.rpm
sudo yum localinstall telegraf-1.9.1-1.x86_64.rpm

#### Mac OS X (for tooling development)
brew install telegraf