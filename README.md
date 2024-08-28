# Renode WebSocket Proxy

Copyright (c) 2024 [Antmicro](https://antmicro.com)

Renode WebSocket Proxy is a session manager and a proxy, enabling both local and remote running and debugging in Renode.

It is utilized by [Renode Extension](https://github.com/antmicro/renode-extension) for VisualStudio Code and Theia.

## Running the proxy

* Locally:

Create a virtual environment and install this package:

```
python3 -m venv venv && . venv/bin/activate
pip install .
```

Run the proxy providing a path to the Renode binary, a working directory and a port to listen on (the plugin defaults to 21234)

```
renode-ws-proxy <RENODE_BINARY> <RENODE_EXECUTION_DIR> <PORT>
```

You can force proxy to run Renode with GUI enabled, by exporting `RENODE_PROXY_GUI_ENABLED` environmental variable.

```sh
export RENODE_PROXY_GUI_ENABLED=1
```

This will also disable creating telnet server in Renode.

* Docker:

```
docker build -t renode-ws-proxy .
docker run -it -P renode-ws-proxy:latest
```

