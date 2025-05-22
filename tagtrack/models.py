from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _


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

    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name='albums')

    def __str__(self):
        return self.name

    class Meta:
        # This ensures we won't be able to create 2 albums with the same name
        # for the same artist
        constraints = [
            models.constraints.UniqueConstraint(
                fields=['artist_id', 'name'], name='unique_artist_album'
            )
        ]


class Song(models.Model):
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='songs')
    duration = models.PositiveSmallIntegerField(
        help_text=_("in seconds"), validators=[MinValueValidator(1)])
    genre = models.CharField(max_length=50, null=True, blank=True)
    number = models.IntegerField(default=1, validators=[MinValueValidator(1)],
                                 help_text=_('Song position in album')
                                 )
    year = models.IntegerField(_('release year'), default=1)

    artists = models.ManyToManyField(Artist, related_name='songs')
    album = models.ForeignKey(Album, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='songs')
    image = models.ImageField(upload_to='singles', null=True, blank=True,
                              help_text=_('Use only for singles'))
    retag = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['album_id', 'number']
