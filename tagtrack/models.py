from django.db import models


class Artist(models.Model):
    name = models.CharField(max_length=200, unique=True)
    image = models.ImageField(upload_to='artists', null=True, blank=True)

    def __str__(self):
        return self.name
