import requests

from .constants import PROTO, API_ADDRESS
from .devices import Room, Sunblind
from .exceptions import APIError
from .helpers import split_data


class Controller:
    host: str
    __url: str
    name: str

    rooms: list = []
    sunblinds: list = []
    sensors: list = []

    def __init__(self, host, name='iqtec_controller'):
        self.host = host
        self.name = name
        self.__url = f"{PROTO}://{host}/{API_ADDRESS}"

    def update(self):
        iot_elements = self.rooms + self.sunblinds + self.sensors
        update_string = ';'.join([element.address for element in iot_elements])
        raw_data = self.__api_request(update_string)
        data_dict = split_data(raw_data)
        for element in iot_elements:
            element.parse_update({key: val for key, val in data_dict.items() if element.address in key})

    def __api_request(self, req: str):
        r = requests.get(f"{self.__url}{req}")
        if r.status_code == requests.codes.ok:
            return r.text
        else:
            raise APIError(
                f"API request '{self.__url}{req}' on platform '{self.name}' failed with HTTP CODE: {r.status_code}!")

    def set_values(self, command_pairs: dict):
        ret = self.__api_request(';'.join([f"{address}={value}" for address, value in command_pairs.items()]))
        ret_values = split_data(ret)
        for a, v in command_pairs.items():
            if a in ret_values.keys() and  str(v) != ret_values.get(a):
                raise APIError(f"Attempted to set value '{v}' at address '{a}' and got {ret_values.get(a)} instead")

    def add_room(self, address: str, name='room') -> Room:
        room = Room(address, self.set_values, name)
        self.rooms.append(room)
        return room

    def add_sunblind(self, address: str, name='sunblind') -> Sunblind:
        sunblind = Sunblind(address, self.set_values, name)
        self.sunblinds.append(sunblind)
        return sunblind
