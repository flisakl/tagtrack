from ninja import ModelSchema, Field, FilterSchema, Schema

from tagtrack.models import Artist, Song, Album


__all__ = [
    'ArtistSchemaIn',
    'ArtistSchemaOut',
    'ArtistFilterSchema',
    'SingleArtistSchemaOut',
]


class ArtistSchemaIn(ModelSchema):
    class Meta:
        model = Artist
        fields = ['name']


class AlbumSchemaIn(ModelSchema):
    artist_id: int

    class Meta:
        model = Album
        fields = ['name', 'genre', 'year']


class SongSchemaIn(ModelSchema):
    album_id: int | None = None
    artist_ids: list[int] = []

    class Meta:
        model = Song
        fields = ['name', 'duration', 'genre', 'year', 'number']


class AlbumSchemaOut(ModelSchema):
    song_count: int | None = None
    total_duration: int | None = None

    class Meta:
        model = Album
        fields = ['id', 'name', 'image', 'genre', 'year']


class ArtistSchemaOut(ModelSchema):
    song_count: int | None = None
    album_count: int | None = None

    class Meta:
        model = Artist
        fields = ['id', 'name', 'image']


class SongSchemaOut(ModelSchema):
    album: AlbumSchemaOut | None = None
    artists: list[ArtistSchemaOut] = None

    class Meta:
        model = Song
        fields = ['id', 'name', 'duration', 'genre', 'year', 'image', 'file',
                  'number']


class ArtistFilterSchema(FilterSchema):
    name: str | None = Field(None, q='name__icontains')
    song_count: int | None = Field(0, q='song_count__gte')
    album_count: int | None = Field(0, q='album_count__gte')


class AlbumFilterSchema(FilterSchema):
    name: str | None = Field(None, q='name__icontains')
    songs_min: int | None = Field(None, q='song_count__gte')
    songs_max: int | None = Field(None, q='song_count__lte')
    year_min: int | None = Field(None, q='year__gte')
    year_max: int | None = Field(None, q='year__lte')
    genre: str | None = Field(None, q='genre__icontains')
    duration_min: int | None = Field(None, q='total_duration__gte',
                                     description='in minutes')
    duration_max: int | None = Field(None, q='total_duration__lte',
                                     description='in minutes')
    artist_id: int | None = Field(None, q='artist__pk')
    artist_name: str | None = Field(None, q='artist__name__icontains')


class SongFilterSchema(FilterSchema):
    name: str | None = Field(None, q='name__icontains')
    year_min: int | None = Field(None, q='year__gte')
    year_max: int | None = Field(None, q='year__lte')
    genre: str | None = Field(None, q='genre__icontains')
    duration_min: int | None = Field(None, q='duration__gte',
                                     description='in seconds')
    duration_max: int | None = Field(None, q='duration__lte',
                                     description='in seconds')
    album_id: int | None = Field(None, q='album__pk')
    album_name: str | None = Field(None, q='album__name__icontains')


class SingleArtistSchemaOut(ModelSchema):
    songs: list[SongSchemaOut] = Field([], alias='songs_sliced')
    albums: list[AlbumSchemaOut] = []

    class Meta:
        model = Artist
        fields = ['id', 'name', 'image']


class SingleAlbumSchemaOut(ModelSchema):
    artist: ArtistSchemaOut
    songs: list[SongSchemaOut] = []
    total_duration: int | None = None
    song_count: int | None = None

    class Meta:
        model = Album
        fields = ['id', 'name', 'image', 'genre', 'year']


class SingleSongSchemaOut(ModelSchema):
    artists: list[ArtistSchemaOut] = []
    album: AlbumSchemaOut | None = None

    class Meta:
        model = Song
        fields = ['name', 'duration', 'genre', 'year', 'image', 'file',
                  'number']


class UploadSchemaOut(Schema):
    total_count: int
    invalid_count: int
    invalid_files: list = []
