# ChargePoint
 ChargePoint coding challenge.


# Additional setup:

```
docker run -d -p 5672:5672 --name cp-rabbitmq rabbitmq
docker run -v /home/redis:/data -p 6379:6379 --name cp-redis -d redis redis-server --save 60 1 --loglevel warning
```