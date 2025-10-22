from django.db import models


class Client(models.Model):
    telegram_id = models.IntegerField()
    hh_resume_link = models.CharField(max_length=200)
    resume_content = models.TextField(null=True, blank=True)
    resume_ontology = models.JSONField(null=True)