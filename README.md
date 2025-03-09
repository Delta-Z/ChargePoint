# ChargePoint coding challenge.

## Architecture

The system consists of 3 Python server nodes + RabbitMQ broker + Redis as storage. I used [Celery](https://docs.celeryq.dev/) for working with the message queue.

I used Redis for simplicity to store the ACLs and the response logs. In reality a more reliable and flexible storage/database might be used depending on the requirements.

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

GET returns a JSON with a single boolean field `allowed`, the PUT and DELETE respond with the `success` status and `new_size` of the station allow list.

### Logging

For each public authorization call, a log record is written to Redis. The log record key is:
`log:authorize:<START_TIME_NS>:<STATION_UUID>:<DRIVER_TOKEN>`. It contains a Redis Hash with the response returned in the callback, the client-supplied `callback_url`, and the status received from the callback.

## Setup

1. Start RabbitMQ:
   ```
   docker run -d -p 5672:5672 --name cp-rabbitmq rabbitmq
   ```

1. Start Redis:
   ```
   export REDIS_PORT=6379
   mkdir -p $HOME/redis && \
     docker run -v $HOME/redis:/data -p $REDIS_PORT:6379 --name cp-redis -d redis \
     redis-server --save 60 1 --loglevel warning
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

### With Docker (doesn't work)

#### Building images:

```
docker build -t authorization_service -f authorization_service.Dockerfile .
docker build -t authorization_worker -f authorization_worker.Dockerfile .
docker build -t public_api -f public_api.Dockerfile .
```

#### Running the images:

Unfortunately I was unable to get all the containers to talk to each other, but if I did, it would probably be something like this:

```
export REDIS_HOST=localhost
export AUTHORIZATION_SERVICE_PORT=5000
docker run -d --name authorization_service -p $AUTHORIZATION_SERVICE_PORT:5000 authorization_service
docker run -d --name authorization_worker --network=host authorization_worker
docker run -d --name public_api -p 8080:8080 public_api
```

Those could also be added to a Docker Compose for convenience.
