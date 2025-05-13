from django.db import models


class Artist(models.Model):
    name = models.CharField(max_length=200, unique=True)
    image = models.ImageField(upload_to='artists', null=True, blank=True)

    def __str__(self):
        return self.name


class Album(models.Model):
    name = models.CharField(max_length=200)
    # Fields below may be blank, because there is no guarantee that uploaded
    # files will hold any metadata
    image = models.ImageField(upload_to='albums', null=True, blank=True)
    genre = models.CharField(max_length=50, null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)

    class Meta:
        # This ensures we won't be able to create 2 albums with the same name
        # for the same artist
        constraints = [
            models.constraints.UniqueConstraint(
                fields=['artist_id', 'name'], name='unique_artist_album'
            )
        ]
