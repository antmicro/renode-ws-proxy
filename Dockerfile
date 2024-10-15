FROM debian:bookworm
RUN apt update && apt upgrade -y && apt install -y --no-install-recommends python3 python3-pip git gdb-multiarch wget

WORKDIR /ws-proxy
COPY . .

RUN pip3 install --break-system-packages .

RUN wget https://builds.renode.io/renode-latest.linux-portable-dotnet.tar.gz -O /tmp/renode-package.tar.gz && \
    mkdir -p /renode-portable /renode-workdir && \
    tar -C /renode-portable --strip-components 1 -xf /tmp/renode-package.tar.gz && \
    rm /tmp/renode-package.tar.gz

EXPOSE 21234
CMD ["renode-ws-proxy", "/renode-portable/renode", "/renode-workdir", "-g", "gdb-multiarch"]
