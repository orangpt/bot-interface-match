from django.db import models


class Client(models.Model):
    SOURCE_URL = "url"
    SOURCE_PDF = "pdf"
    SOURCE_MD = "md"
    SOURCE_CHOICES = [
        (SOURCE_URL, "Ссылка HH.ru"),
        (SOURCE_PDF, "PDF"),
        (SOURCE_MD, "Markdown"),
    ]

    telegram_id = models.IntegerField()
    source_type = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_URL
    )
    hh_resume_link = models.CharField(max_length=500, blank=True, null=True)
    resume_content = models.TextField(null=True, blank=True)
    resume_ontology = models.JSONField(null=True)