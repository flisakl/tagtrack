from ninja import Router, Schema, FilterSchema, Query
from django.db.models import Count, Sum
from asgiref.sync import sync_to_async
from django.core.cache import cache

from tagtrack import AUTH
from tagtrack.models import Artist, Song, Album
from tagtrack import utils
from .schemas import (
    ArtistSchemaOut, ArtistFilterSchema,
    AlbumFilterSchema, AlbumWithArtistSchemaOut,
    SongSchemaOut, SongFilterSchema
)
from mutagen._constants import GENRES


router = Router(tags=['Generic'])


class CombinedSchema(Schema):
    artists: list[ArtistSchemaOut]
    albums: list[AlbumWithArtistSchemaOut]
    songs: list[SongSchemaOut]


class CombinedFilterSchema(FilterSchema):
    name: str | None = None
    genre: str | None = None
    album_name: str | None = None
    song_count: int | None = None
    album_count: int | None = None
    songs_min: int | None = None
    songs_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    duration_min: int | None = None
    duration_max: int | None = None
    album_id: int | None = None


class GenreSchemaOut(Schema):
    items: list[dict]


def _gen_dict(keys: list[str], filter: CombinedFilterSchema) -> dict:
    ret = {}
    for key in keys:
        ret[key] = getattr(filter, key)
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

    return {
        'artists': artists,
        'songs': songs,
        'albums': albums,
    }
