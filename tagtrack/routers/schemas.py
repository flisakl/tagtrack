from ninja import ModelSchema, Field, FilterSchema

from tagtrack.models import Artist, Song, Album


__all__ = [
    'ArtistSchemaIn',
    'ArtistSchemaOut',
]


class ArtistSchemaIn(ModelSchema):
    class Meta:
        model = Artist
        fields = ['name']


class SongSchemaOut(ModelSchema):
    class Meta:
        model = Song
        fields = ['id', 'name', 'duration', 'genre', 'year', 'image', 'file',
                  ]


class AlbumSchemaOut(ModelSchema):
    class Meta:
        model = Album
        fields = ['id', 'name', 'image', 'genre', 'year']


class ArtistSchemaOut(ArtistSchemaIn):
    song_count: int = 0
    album_count: int = 0

    class Meta:
        fields = ['id', 'name', 'image']


class ArtistFilterSchema(FilterSchema):
    name: str | None = Field(None, q='name__icontains')
    song_count: int | None = Field(0, q='song_count__gte')
    album_count: int | None = Field(0, q='album_count__gte')


class SingleArtistSchemaOut(ArtistSchemaOut):
    songs: list[SongSchemaOut] = []
    albums: list[AlbumSchemaOut] = []
