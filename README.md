# ChargePoint coding challenge.

## Architecture

The system consists of 3 Python server nodes + RabbitMQ broker + Redis / Elasticsearch as storage. I used [Celery](https://docs.celeryq.dev/) for working with the message queue.

The ACLs are stored in Redis for simplicity. In reality a more reliable and flexible storage/database might be used depending on the requirements.

Response logs can be stored in Elasticsearch or Redis (the former by default).

The 3 server nodes are:

*  Public API service which returns the acknowledgement to the user and enqueues the authorization task.
*  Authorization Worker which polls authorization tasks from the message queue, queries the Authorization Service, calls the callback and logs the response.
*  Authorization Service which exposes the ACLs as a REST API.

Authorization Service and Public API service are Flask development servers (because I don't know any better :).

## API documentation

### Public authorization API

The public API on port 8080 responds to URLs in the form of:

`/station/<STATION_UUID>/driver/<DRIVER_TOKEN>/authorize?callback_url=<CALLBACK_URL>`

It accepts both GET and POST requests, in the latter case `callback_url` can also be passed in JSON.

The result is returned via a POST call to the `callback_url`.

### Internal access list API

The access list is kept in Redis, as a set of allowed driver tokens per station, stored under `station:<STATION_UUID>:allowlist`.

The internal authorization service runs on port 5000 and exposes the endpoint `/station/<STATION_UUID>/driver/<DRIVER_TOKEN>/acl`, which supports GET, PUT, and DELETE methods for checking, adding, and removing driver access accordingly.

GET returns a JSON with a single boolean field `allowed`, the PUT and DELETE respond with the number of acls added/removed (should be 1 or 0).

Example of adding ACL with `curl`:
```
curl -X PUT http://localhost:5000/station/123e4567-e89b-12d3-a456-426614174000/driver/validDriverToken4321/acl
```

### Logging

For each public authorization call, a log record is written.

If `authorization_worker` sees the `ELASTICSEARCH_URL` environment variable, it will try to log to Elasticsearch. If the `REDIS_HOST` variable
is present, it will try to log to Redis. If neither is available, logging is skipped.

#### Elasticsearch

The log entries are written to the `log.authorize` index. For schema, see `authorization_worker/elastic_logger.py`.

#### Redis

The log record key is:
`log:authorize:<START_TIME_NS>:<STATION_UUID>:<DRIVER_TOKEN>`. It contains a Redis Hash with the response returned in the callback, the client-supplied `callback_url`, and the status received from the callback.

Example of accessing the logs with Redis CLI:

```
docker run --network cp-auth_default -it --rm redis redis-cli -h cp-auth-redis-1
```

## Running the system

### With Docker

`docker compose up`

#### Accessing the storage

Example running Redis CLI:

```
docker run --network cp-auth_default -it --rm redis redis-cli -h cp-auth-redis-1
```

Example searching auhtorization event logs in Elastic with `curl`:

```
 curl --cacert /var/lib/docker/volumes/cp-auth_elastic-config/_data/certs/http_ca.crt -u elastic:shiboleth https://localhost:9200/log.authorize/_search
```

### Without Docker

1. Install Python package requirements: `pip install -r requirements.txt`.

Note that some environment variables below are shared (in particular `AUTHORIZATION_SERVICE_PORT`).

1. Configure and start the authorization server:
   ```
   export REDIS_HOST=localhost
   export AUTHORIZATION_SERVICE_PORT=5000
   flask --app authorization_service.app run --port $AUTHORIZATION_SERVICE_PORT &
   ```

1. Configure and start the RabbitMQ worker:
   ```
   export AUTHORIZATION_SERVICE_URL=http://localhost:$AUTHORIZATION_SERVICE_PORT
   export CALLBACK_TIMEOUT_SEC=5
   celery -A authorization_worker.tasks worker --loglevel=INFO &
   ```
   
1. Configure and start the public API:
   ```
   export AUTHORIZATION_TIMEOUT_SEC=5
   flask --app public_api.app run --port 8080 &
   ```
