import redis

from authorization_worker.logger import Logger


class RedisLogger(Logger):
    """Logs authorization events to Redis."""
    def __init__(self, redis_host: str, redis_port: int):
        self._redis_client = redis.Redis(redis_host, redis_port)
        print(f"Connected to {self._redis_client.info('server')}.")

    def log_authorize(self, start_time_ns: int, log_data: dict[str, str]):
        if self._redis_client is None:
            self.initialize_clients()
            assert self.redis_client is not None
        self._redis_client.hset(
            f"log:authorize:{start_time_ns}:{log_data['station_id']}:{log_data['driver_token']}",
            mapping=log_data,
        )
