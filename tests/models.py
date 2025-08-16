from __future__ import annotations

from django.db import models


class QSignalsModel(models.Model):
    name = models.CharField(max_length=100)
    value = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
