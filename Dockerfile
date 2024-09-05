FROM antmicro/renode:nightly-dotnet
RUN apt update && apt upgrade && apt install -y --no-install-recommends python3 python3-pip gdb-multiarch

COPY . .
WORKDIR .

RUN pip3 install . 
RUN mkdir /tmp/renode

EXPOSE 21234
CMD ["renode-ws-proxy", "/opt/renode/renode", "/tmp/renode", "gdb-multiarch", "21234"]

