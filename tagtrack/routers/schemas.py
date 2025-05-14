from ninja import ModelSchema

from tagtrack.models import Artist


__all__ = [
    'ArtistSchemaIn',
    'ArtistSchemaOut',
]


class ArtistSchemaIn(ModelSchema):
    class Meta:
        model = Artist
        fields = ['name']


class ArtistSchemaOut(ArtistSchemaIn):
    song_count: int = 0
    album_count: int = 0

    class Meta:
        fields = ['id', 'name', 'image']
