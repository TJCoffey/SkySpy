# SkySpy

Build the SkySpy container (from the SkySpy/SkySpy directory):
```sh
$ docker build -t tjcoffey/skyspy .
```

Set the `DATA_DIR` environment variable to the path where will be stored local data (e.g. in `/nas/docker`):

```sh
export DATA_DIR=/nas/docker
```

Create data directories with write access:

```sh
mkdir -p ${DATA_DIR}/influxdb ${DATA_DIR}/grafana
sudo chown -R 472:472 ${DATA_DIR}/grafana
```

Run docker compose:

```sh
$ docker-compose up -d
```