from datetime import datetime, timedelta


# Timeout is handled in 5 minute increments the system checks for
def encode_timeout(t: datetime) -> int:
    now = datetime.now()
    now = now.replace(second=0, microsecond=0, minute=now.minute // 5 * 5)
    delta = t - now
    seconds = delta.total_seconds()
    return max(int(seconds // 60 // 5), 1)  # make at least one 5 min interval, otherwise interval is rounded down


def decode_timeout(t: int) -> datetime:
    now = datetime.now()
    now = now.replace(second=0, microsecond=0, minute=now.minute // 5 * 5)
    return now + timedelta(minutes=t * 5)


def remove_whitespaces(s: str) -> str:
    return ''.join(s.split())


def split_data(raw_data: str) -> dict:
    data_list = filter(lambda l: '=' in l, raw_data.split('\r\n'))
    data_dict = dict(line.split('=', 1) for line in data_list)
    return data_dict
