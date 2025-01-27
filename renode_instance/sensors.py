# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import cast

from System import Decimal
from Antmicro.Renode.Peripherals.Sensor import (
    ISensor,
    ITemperatureSensor,
    IADC,
    IHumiditySensor,
    IMagneticSensor,
)

from renode_instance.state import State, Command
from renode_instance.utils import csharp_is, csharp_as, get_full_name

MAX_UINT = (1 << 32) - 1
MAX_INT = (1 << 31) - 1
MIN_INT = -(1 << 31)

command = Command()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sensors.py")

sensor_type = {
    "temperature": ITemperatureSensor,
    # "acceleration": ,
    # "angular-rate": ,
    "voltage": IADC,
    # "ecg": ,
    "humidity": IHumiditySensor,
    # "pressure": ,
    "magnetic-flux-density": IMagneticSensor,
}


def assert_3d(value, minv: int, maxv: int):
    assert minv <= value["x"] <= maxv
    assert minv <= value["y"] <= maxv
    assert minv <= value["z"] <= maxv


def set_magnetic_sensor_data(obj: IMagneticSensor, value):
    assert_3d(value, MIN_INT, MAX_INT)
    obj.MagneticFluxDensityX = value["x"]
    obj.MagneticFluxDensityY = value["y"]
    obj.MagneticFluxDensityZ = value["z"]


def get_magnetic_sensor_data(obj: IMagneticSensor):
    return {
        "x": obj.MagneticFluxDensityX,
        "y": obj.MagneticFluxDensityY,
        "z": obj.MagneticFluxDensityZ,
    }


def set_temperature(obj: ITemperatureSensor, value: int):
    assert MIN_INT <= value <= MAX_INT
    obj.Temperature = Decimal(int(value) / 1e3)


def set_voltage(obj: IADC, value: int):
    assert 0 <= value <= MAX_UINT
    obj.SetADCValue(0, value)


def set_humidity(obj: IHumiditySensor, value: int):
    assert 0 <= value <= MAX_UINT
    obj.Humidity = Decimal(int(value) / 1e3)


sensor_setter = {
    "temperature": lambda obj, value: set_temperature(
        cast(ITemperatureSensor, obj), value
    ),
    "voltage": lambda obj, value: set_voltage(cast(IADC, obj), value),
    "humidity": lambda obj, value: set_humidity(cast(IHumiditySensor, obj), value),
    "magnetic-flux-density": lambda obj, value: set_magnetic_sensor_data(
        cast(IMagneticSensor, obj), value
    ),
}

sensor_getter = {
    "temperature": lambda obj: int(
        Decimal.ToDouble(cast(ITemperatureSensor, obj).Temperature) * 1e3
    ),
    "voltage": lambda obj: cast(IADC, obj).GetADCValue(0),
    "humidity": lambda obj: int(
        Decimal.ToDouble(cast(IHumiditySensor, obj).Humidity) * 1e3
    ),
    "magnetic-flux-density": lambda obj: get_magnetic_sensor_data(
        cast(IMagneticSensor, obj)
    ),
}


@command.register
def sensors(state: State, message):
    if "machine" not in message:
        return {"err": "missing required argument 'machine'"}

    machine = state.emulation.get_mach(message["machine"])

    if not machine:
        return {"err": "provided machine does not exist"}

    type = ISensor
    if "type" in message:
        msg_type = message["type"]
        if msg_type not in sensor_type:
            return {"err": f"not supported 'type' value: '{msg_type}'"}
        type = sensor_type[msg_type]

    instances = machine.internal.GetPeripheralsOfType[type]()
    instance_names = [
        (get_full_name(instance, machine), instance) for instance in instances
    ]

    sensor_instances = [
        {
            "name": name,
            "types": [
                stype_name
                for stype_name, stype in sensor_type.items()
                if csharp_is(stype, instance)
            ],
        }
        for name, instance in instance_names
        if name
    ]

    return {"rsp": sensor_instances}


@command.register
def sensor_set(state: State, message):
    for argument in ["machine", "peripheral", "type", "value"]:
        if argument not in message:
            return {"err": f"missing required argument '{argument}'"}

    machine = state.emulation.get_mach(message["machine"])
    if not machine:
        return {"err": "provided machine does not exist"}
    type = message["type"]
    periph_name = message["peripheral"]
    ok, perpheral = machine.internal.TryGetByName[sensor_type[type]](periph_name)
    if not ok:
        return {"err": f"peripheral {periph_name} implementing '{type}' not found"}
    value = message["value"]

    sensor_setter[type](perpheral, value)
    return {"rsp": "ok"}


@command.register
def sensor_get(state: State, message):
    for argument in ["machine", "peripheral", "type"]:
        if argument not in message:
            return {"err": f"missing required argument '{argument}'"}

    machine = state.emulation.get_mach(message["machine"])
    if not machine:
        return {"err": "provided machine does not exist"}
    type = message["type"]
    periph_name = message["peripheral"]
    perpheral = machine.internal[periph_name]
    sensor = csharp_as(sensor_type[type], perpheral)

    if sensor is None:
        return {"err": f"peripheral {periph_name} implementing '{type}' not found"}

    return {"rsp": sensor_getter[type](sensor)}
