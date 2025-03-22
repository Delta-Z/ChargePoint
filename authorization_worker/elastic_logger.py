from typing import Optional

from elasticsearch_dsl import Document, Long, connections

from authorization_worker.logger import Logger


class AuthorizationLogEntry(Document):
    """Log entry for authorization events."""
    station_id: str
    driver_token: str
    status: str
    callback_status: Optional[str]
    callback_url: Optional[str]
    start_time_ms = Long(required=True)

    class Index:
        name = "log.authorize"


class ElasticLogger(Logger):
    """Logs authorization events to Elasticsearch."""
    def __init__(
        self,
        elasticsearch_url: str,
        elastic_password: str,
        ca_cert_dir: str | None = None,
    ):
        self._elasticsearch_client = connections.create_connection(
            hosts=elasticsearch_url,
            ssl_assert_hostname=False,
            ca_certs=ca_cert_dir,
            timeout=10,
            basic_auth=("elastic", elastic_password),
        )
        print(f"Connected to {self._elasticsearch_client.info()}")
        AuthorizationLogEntry.init(using=self._elasticsearch_client)

    def log_authorize(self, start_time_ns: int, log_data: dict[str, str]):
        AuthorizationLogEntry(
            station_id=log_data["station_id"],
            driver_token=log_data["driver_token"],
            status=log_data["status"],
            callback_status=log_data.get("callback_status"),
            callback_url=log_data.get("callback_url"),
            start_time_ms=start_time_ns // 1_000_000,
        ).save(using=self._elasticsearch_client)
