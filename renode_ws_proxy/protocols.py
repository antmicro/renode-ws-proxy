# Copyright (c) 2025 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict

DATA_PROTOCOL_VERSION = "1.1.0"
MAJOR, MINOR, PATCH = DATA_PROTOCOL_VERSION.split(".")

_SUCCESS = "success"
_FAIL = "failure"


@dataclass
class Message:
    version: str
    action: str
    id: int
    payload: Optional[Dict[str, Any]] = field(default_factory=dict)
    status: Optional[str] = None
    error: Optional[str] = None

    def to_json(self) -> str:
        """Serialize the message to a JSON string."""
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(json_str: str) -> "Message":
        """Deserialize a JSON string to a Message object."""
        data = json.loads(json_str)
        return Message(**data)

    def validate(self):
        major, minor, patch = self.version.split(".")
        if major != MAJOR:
            raise Exception("Incompatible protocol version detected")


@dataclass
class Response:
    version: str
    status: str
    id: Optional[int] = None
    data: Optional[Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_json(self) -> str:
        """Serialize the response to a JSON string."""
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(json_str: str) -> "Response":
        """Deserialize a JSON string to a Response object."""
        data = json.loads(json_str)
        return Response(**data)


@dataclass
class Event:
    version: str
    event: str
    data: Optional[Dict[str, Any]] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize the message to a JSON string."""
        return json.dumps(asdict(self))

    @staticmethod
    def from_renode_event(event: dict) -> "Event":
        """Deserialize a JSON string to a Message object."""
        return Event(
            version=DATA_PROTOCOL_VERSION, event=event.pop("event"), data=event
        )


if __name__ == "__main__":
    json_str = Message(
        version="1.0", action="create", id=0, payload={"id": 123, "name": "test"}
    ).to_json()
    print("Serialized JSON:", json_str)
    msg_received = Message.from_json(json_str)
    print("Deserialized Message:", msg_received)

    print()

    resp_json_str = Response(
        version="1.0", status="success", id=0, data={"id": 123, "name": "test"}
    ).to_json()
    print("Serialized Response JSON:", resp_json_str)
    resp_received = Response.from_json(resp_json_str)
    print("Deserialized Response:", resp_received)
