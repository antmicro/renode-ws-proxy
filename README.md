# Renode WebSocket Proxy

Copyright (c) 2024 [Antmicro](https://antmicro.com)

Renode WebSocket Proxy is a session manager and a proxy, enabling both local and remote running and debugging in Renode.

It is utilized by [Renode Extension](https://github.com/antmicro/renode-extension) for VisualStudio Code and Theia.

## Running the proxy

- Locally:

Create a virtual environment and install this package:

```
python3 -m venv venv && . venv/bin/activate
pip install .
```

Download and extract Renode Dotnet portable package:

```
wget https://builds.renode.io/renode-latest.linux-portable-dotnet.tar.gz
tar xf renode-latest.linux-portable-dotnet.tar.gz
```

Run the proxy providing a path to the Renode portable binary, a working directory and a port to listen on (the plugin defaults to 21234)

```
renode-ws-proxy [-g GDB] [-p PORT] <renode_binary> <renode_execution_dir>
```

You can disable option to run Renode with GUI, by exporting `RENODE_PROXY_GUI_DISABLED` environmental variable.

```sh
export RENODE_PROXY_GUI_DISABLED=1
```

- Docker:

```
docker build -t renode-ws-proxy .
docker run -it -P renode-ws-proxy:latest
```
