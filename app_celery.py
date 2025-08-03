from celery import Celery
import os

rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://admin:admin@rabbitmq:5672//')
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')

celery_app = Celery(
    "tenders_parser",
    broker=rabbitmq_url,
    backend=redis_url,
)

import tasks