class Logger:
    """Base class for logging authorization events. Does nothing."""

    def log_authorize(self, start_time_ns: int, log_data: dict[str, str]):
        pass
