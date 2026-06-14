from faststream.rabbit import RabbitBroker

broker = RabbitBroker(
    "amqp://guest:guest@localhost:5672/"
)