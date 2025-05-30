from celery import Celery


app = Celery("app")
app.config_from_object("django.conf:settings", namespace="CELERY")
