PROTO = 'http'
API_ADDRESS = 'control/?'

ROOM_MODE = {
    'calendar': 0,
    'day': 1,
    'night': 2,
    'manual': 3,
}

ROOM_API = {
    'requested_temperature': '38',
    'mode': '49',
    'timeout': '54',
    'calendar_number': '25',
    'internal_name': '8',
    # read-only
    'temperature': '36',
    'heating_on': '41/1',
}

SUNBLIND_API = {
    'move_time': '12',  # used to calculate position internally in seconds
    # other times in microseconds
    'reverse_time': '14',
    'tilt_time': '16',
    'short_down_time': '18',
    'step_time': '20',
    'full_tilt_time': '22',  # used to calculate rotation internally
    # read-only
    'position': '42',
    'rotation': '41',
    'command': '50',
    'disabled': '7/1'
}

SUNBLIND_COMMANDS = {
    'up': 0,  # move_time
    'down': 1,  # move_time
    'down_open': 2,  # move_time + reverse_time + tilt_time
    'stop': 3,
    'open': 4,  # short_down_time + reverse_time + tilt_time
    'step_up': 5,  # step_time
    'step_down': 6,  # step_time
    'up_and_disable': 7,  # move_time
    'enable': 8,
    'open_short': 9,  # tilt_time
}

SUNBLIND_TILT_OPEN = 0
SUNBLIND_TILT_CLOSED = 180
SUNBLIND_FULL_RETRACTED = 0
SUNBLIND_FULL_EXTENDED = 1000
