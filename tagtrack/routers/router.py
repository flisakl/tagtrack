from ninja import Router, Schema, FilterSchema, Query, Field
from django.db.models import Count, Sum
from asgiref.sync import sync_to_async
from django.core.cache import cache
from urllib.parse import urlencode

from tagtrack import AUTH
from tagtrack.models import Artist, Song, Album
from tagtrack import utils
from .schemas import (
    ArtistSchemaOut, ArtistFilterSchema,
    AlbumFilterSchema, AlbumWithArtistSchemaOut,
    SongSchemaOut, SongFilterSchema, Genre, PositiveInt
)
from mutagen._constants import GENRES


router = Router(tags=['Generic'])


class CombinedSchema(Schema):
    artists: list[ArtistSchemaOut]
    albums: list[AlbumWithArtistSchemaOut]
    songs: list[SongSchemaOut]


class CombinedFilterSchema(FilterSchema):
    name: str = Field(None)
    album_name: str = Field(None)
    song_count: int = Field(None, ge=0, q='song_count__gte')
    album_count: int = Field(None, ge=0, q='album_count__gte')
    songs_min: int = Field(None, ge=0, q='song_count__gte')
    songs_max: int = Field(None, ge=0, q='song_count__lte')
    album_id: PositiveInt = Field(None)
    year_min: int = Field(None, ge=0, q='year__gte')
    year_max: int = Field(None, ge=0, q='year__lte')
    genre: Genre = Field(None, q='genre__icontains')
    duration_min: int = Field(None, ge=0, q='total_duration__gte', description='in minutes')
    duration_max: int = Field(None, ge=0, q='total_duration__lte', description='in minutes')


class GenreSchemaOut(Schema):
    items: list[dict]


def _gen_dict(keys: list[str], filter: CombinedFilterSchema) -> dict:
    ret = {}
    for key in keys:
        if value := getattr(filter, key):
            ret[key] = value
    return ret


@router.get(
    '/genres',
    response=GenreSchemaOut,
    auth=AUTH['READ'],
    description='Collection of valid genres'
)
async def get_genres(request):
    key = "tagtrack-genres"
    data = await sync_to_async(cache.get)(key, None)
    if data:
        return {'items': data}
    data = [{'name': x} for x in GENRES]
    await sync_to_async(cache.set)(key, data)
    return {'items': data}


@router.get(
    '/search',
    response=CombinedSchema,
    auth=AUTH['READ'],
    description='Generic search for all models',
    exclude_none=True,
    exclude_unset=True
)
async def search(
    request,
    filters: Query[CombinedFilterSchema]
):
    key = f"tagtrack-search:{urlencode(sorted(request.GET.items()), doseq=True)}"
    data = await sync_to_async(cache.get)(key, None)
    if data:
        return data

    alb_filters = AlbumFilterSchema(
        **_gen_dict(['name', 'year_min', 'year_max', 'genre', 'duration_min',
                     'duration_max', 'album_id', 'album_name'], filters)
    )
    art_filters = ArtistFilterSchema(
        **_gen_dict(['name', 'song_count', 'album_count'], filters)
    )
    song_filters = SongFilterSchema(
        **_gen_dict(['name', 'year_min', 'year_max', 'genre', 'duration_min',
                     'duration_max', 'album_id', 'album_name'], filters)
    )
    alb_qs = Album.objects.select_related('artist').annotate(
        song_count=Count('songs', distinct=True),
        total_duration=Sum('songs__duration') / 60
    )
    art_qs = Artist.objects.annotate(
        song_count=Count('songs', distinct=True),
        album_count=Count('albums', distinct=True),
    )
    song_qs = Song.objects.select_related('album').prefetch_related('artists')
    albums = await sync_to_async(list)(alb_filters.filter(alb_qs)[:20])
    artists = await sync_to_async(list)(art_filters.filter(art_qs)[:20])
    songs = await sync_to_async(list)(song_filters.filter(song_qs)[:20])

    for song in songs:
        utils.fill_song_fields(song, song.album)

    data = {
        'artists': artists,
        'songs': songs,
        'albums': albums,
    }
    await sync_to_async(cache.set)(key, data)
    return data
