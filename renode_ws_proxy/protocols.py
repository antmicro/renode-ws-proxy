# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict

DATA_PROTOCOL_VERSION = "0.0.1"

_SUCCESS = "success"
_FAIL = "failure"

@dataclass
class Message:
    version: str
    action: str
    payload: Optional[Dict[str, Any]] = field(default_factory=dict)
    status: Optional[str] = None
    error: Optional[str] = None

    def to_json(self) -> str:
        """Serialize the message to a JSON string."""
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(json_str: str) -> 'Message':
        """Deserialize a JSON string to a Message object."""
        data = json.loads(json_str)
        return Message(**data)


@dataclass
class Response:
    version: str
    status: str
    data: Optional[Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_json(self) -> str:
        """Serialize the response to a JSON string."""
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(json_str: str) -> 'Response':
        """Deserialize a JSON string to a Response object."""
        data = json.loads(json_str)
        return Response(**data)


if __name__ == "__main__":
    json_str = Message(version="1.0", action="create", payload={"id": 123, "name": "test"}).to_json()
    print("Serialized JSON:", json_str)
    msg_received = Message.from_json(json_str)
    print("Deserialized Message:", msg_received)

    print()

    resp_json_str = Response(version="1.0", status="success", data={"id": 123, "name": "test"}).to_json()
    print("Serialized Response JSON:", resp_json_str)
    resp_received = Response.from_json(resp_json_str)
    print("Deserialized Response:", resp_received)
