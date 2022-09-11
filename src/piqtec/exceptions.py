class APIError(Exception):
    """Raised when request does not complete successfully"""
    pass


class DeviceException(Exception):
    def __init__(self, device_name, address, message=""):
        self.device_name = device_name
        self.address = address
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.device_name}:{self.address}:{self.message}"

class InvalidSetCommand(DeviceException):
    """Raised when attempting to set a wrong value"""
    pass


class UpdateError(DeviceException):
    """Raised when data for update are not as expected"""
    pass


class ConfigurationError(DeviceException):
    """Raised when interface is misconfigured"""
    pass
