from ninja import ModelSchema, Field, FilterSchema, Schema
from pydantic import AfterValidator
from typing import Annotated, TypeVar
from annotated_types import Len, Gt
from mutagen._constants import GENRES
from django.utils.translation import gettext_lazy as _

from tagtrack.models import Artist, Song, Album

LOWER_GENRES = [x.lower() for x in GENRES]


def is_mutagen_genre(value: str):
    if value.lower() not in LOWER_GENRES:
        raise ValueError(_('Invalid genre'))
    return value


# Custom types
T = TypeVar('T')

PositiveInt = Annotated[int, Field(gt=0)]
ArtistIDList = Annotated[list[PositiveInt], Len(min_length=1)]
Genre = Annotated[str, AfterValidator(is_mutagen_genre)]


__all__ = [
    'ArtistSchemaIn',
    'ArtistSchemaOut',
    'ArtistFilterSchema',
    'SingleArtistSchemaOut',
]


class ArtistSchemaIn(Schema):
    name: str = Field(min_length=1)


class AlbumSchemaIn(Schema):
    name: str = Field(min_length=1)
    artist_id: PositiveInt
    year: PositiveInt = Field(None)
    genre: Genre = Field(None)


class SongSchemaIn(Schema):
    album_id: PositiveInt
    artist_ids: ArtistIDList
    genre: Genre = Field(None)
    year: PositiveInt = Field(None)
    number: PositiveInt = Field(None)
    duration: PositiveInt
    name: str = Field(min_length=1)


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


class AlbumWithArtistSchemaOut(ModelSchema):
    song_count: int | None = None
    total_duration: int | None = None
    artist: ArtistSchemaOut = None

    class Meta:
        model = Album
        fields = ['id', 'name', 'image', 'genre', 'year']


class SongSchemaOut(ModelSchema):
    album: AlbumSchemaOut | None = None
    artists: list[ArtistSchemaOut] = None

    class Meta:
        model = Song
        fields = ['id', 'name', 'duration', 'genre', 'year', 'image', 'file',
                  'number']


class ArtistFilterSchema(FilterSchema):
    name: str = Field(None, q='name__icontains')
    song_count: int = Field(0, ge=0, q='song_count__gte')
    album_count: int = Field(0, ge=0, q='album_count__gte')


class AlbumFilterSchema(FilterSchema):
    name: str = Field(None, q='name__icontains')
    songs_min: int = Field(None, ge=0, q='song_count__gte')
    songs_max: int = Field(None, ge=0, q='song_count__lte')
    year_min: int = Field(None, ge=0, q='year__gte')
    year_max: int = Field(None, ge=0, q='year__lte')
    genre: Genre = Field(None, q='genre__icontains')
    duration_min: int = Field(None, ge=0, q='total_duration__gte', description='in minutes')
    duration_max: int = Field(None, ge=0, q='total_duration__lte', description='in minutes')
    artist_id: PositiveInt = Field(None, q='artist__pk')
    artist_name: str = Field(None, q='artist__name__icontains')


class SongFilterSchema(FilterSchema):
    name: str = Field(None, q='name__icontains')
    year_min: int = Field(None, ge=0, q='year__gte')
    year_max: int = Field(None, ge=0, q='year__lte')
    genre: Genre = Field(None, q='genre__icontains')
    duration_min: int = Field(None, ge=0, q='duration__gte', description='in minutes')
    duration_max: int = Field(None, ge=0, q='duration__lte', description='in minutes')
    album_id: PositiveInt = Field(None, q='album__pk')
    album_name: str = Field(None, q='album__name__icontains')


class SingleArtistSchemaOut(ModelSchema):
    albums: list[AlbumSchemaOut] = []
    song_count: int | None = None
    album_count: int | None = None

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
        fields = ['id', 'name', 'duration', 'genre', 'year', 'image', 'file',
                  'number']


class UploadSchemaOut(Schema):
    total_count: int
    invalid_count: int
    invalid_files: list = []
