from ninja import Router, Form, File, UploadedFile, Query
from ninja.pagination import LimitOffsetPagination
from django.core.cache import cache
from django.db.models import Count, QuerySet
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django.shortcuts import aget_object_or_404
from ninja.errors import ValidationError
from ninja.pagination import paginate
from asgiref.sync import sync_to_async
from urllib.parse import urlencode

from tagtrack import ARTIST_AUTH
from tagtrack import utils
from tagtrack.models import Artist, Song
from .schemas import (
    ArtistSchemaIn, ArtistSchemaOut, ArtistFilterSchema, SingleArtistSchemaOut,
    SongSchemaOut
)

router = Router(tags=["Artists"])


class CustomLimitPagination(LimitOffsetPagination):
    def __init__(
        self,
        limit: int = None,
        offset: int = None,
        **kwargs: any,
    ) -> None:
        self.limit = limit
        self.offset = offset
        super().__init__(**kwargs)

    def paginate_queryset(
        self,
        queryset: any,
        pagination: any,
        **params: any,
    ) -> any:
        offset = self.offset or pagination.offset
        limit: int = min(self.limit or pagination.limit, 100)
        return {
            "items": queryset[offset:offset + limit],
            "count": self._items_count(queryset),
        }

    async def apaginate_queryset(
        self,
        queryset: any,
        pagination: any,
        **params: any,
    ) -> any:
        offset = self.offset or pagination.offset
        limit: int = min(self.limit or pagination.limit, 100)
        if isinstance(queryset, QuerySet):
            items = [obj async for obj in queryset[offset:offset + limit]]
        else:
            items = queryset[offset:offset + limit]
        return {
            "items": items,
            "count": await self._aitems_count(queryset),
        }


@router.post(
    '',
    response={201: ArtistSchemaOut},
    auth=ARTIST_AUTH['CREATE'],
    description="Create a new artist with optional image upload."
)
async def create_artist(
    request,
    form: Form[ArtistSchemaIn],
    image: UploadedFile | None = File(None)
):
    """
    Creates a new artist entry.

    - Validates optional uploaded image.
    - Saves the artist to the database.
    - Returns HTTP 201 on success or validation error on duplicate name.
    """
    artist = Artist(**form.dict(exclude_unset=True))

    await sync_to_async(utils.raise_on_invalid_image)(image)
    artist.image = image

    try:
        await artist.asave()
        return 201, artist
    except IntegrityError:
        raise ValidationError([
            utils.make_error(['form'], 'name', _('Artist already exists'))
        ])


@router.get(
    '',
    response=list[ArtistSchemaOut],
    auth=ARTIST_AUTH['READ'],
    description="Retrieve a paginated list of artists with optional filtering.",
    exclude_unset=True,
    exclude_none=True
)
@paginate
async def get_artists(
    request,
    filters: Query[ArtistFilterSchema],
):
    """
    Retrieves a paginated list of artists.

    - Supports filtering through query parameters.
    - Annotates artist entries with counts of related songs and albums.
    - Results are cached by querystring.
    """
    key = f"artists:{urlencode(sorted(request.GET.items()), doseq=True)}"
    qs = filters.filter(Artist.objects.annotate(
        song_count=Count('songs', distinct=True),
        album_count=Count('albums', distinct=True)
    ))
    return await utils.get_or_set_from_cache(key, qs)


@router.get(
    '/{int:artist_id}',
    response=SingleArtistSchemaOut,
    auth=ARTIST_AUTH['READ'],
    description="Retrieve details for a specific artist by ID.",
    exclude_unset=True,
    exclude_none=True
)
async def get_artist(
    request,
    artist_id: int,
):
    """
    Retrieves detailed information about a specific artist.

    - Annotates artist with song and album counts.
    - Prefetches related albums.
    - Caches the response by artist ID.
    """
    key = f"artists:artist_id={artist_id}"
    qs = Artist.objects.prefetch_related('albums').annotate(
        song_count=Count('songs', distinct=True),
        album_count=Count('albums', distinct=True)
    )
    obj = await utils.get_or_set_from_cache(key, qs, artist_id)
    return obj


@router.get(
    '/{int:artist_id}/songs',
    response=list[SongSchemaOut],
    auth=ARTIST_AUTH['READ'],
    description="Retrieve songs from artist with given ID.",
    exclude_unset=True
)
@paginate(CustomLimitPagination, limit=20)
async def get_artist_songs(
    request,
    artist_id: int,
):
    """
    Retrieves songs made by artist with given ID.
    - Prefetches album and artists for each song.
    - Caches the response by artist ID.
    """
    key = f"artists-songs:artist_id={artist_id}"
    qs = Song.objects.select_related('album').prefetch_related(
        'artists').filter(artists__id__in=[artist_id])
    objs = await utils.get_or_set_from_cache(key, qs)
    return objs


@router.patch(
    '/{int:artist_id}',
    response=ArtistSchemaOut,
    auth=ARTIST_AUTH['UPDATE'],
    description="Update an existing artist by ID, including optional image replacement.",
)
async def update_artist(
    request,
    artist_id: int,
    form: Form[ArtistSchemaIn],
    image: UploadedFile | None = File(None)
):
    """
    Updates an existing artist.

    - Applies partial updates from the input form.
    - Optionally replaces the artist image after validation.
    - Deletes the cached record before returning the updated artist.
    """
    data = form.dict(exclude_unset=True)
    obj = await aget_object_or_404(Artist, pk=artist_id)

    for attr, value in data.items():
        setattr(obj, attr, value)

    if image:
        await sync_to_async(utils.raise_on_invalid_image)(image)
        await sync_to_async(obj.image.delete)(save=False)
        await sync_to_async(obj.image.save)(image.name, image, save=False)

    try:
        await obj.asave()
    except IntegrityError:
        raise ValidationError([
            utils.make_error(['form'], 'name', _('Artist already exists'))
        ])

    key = f"artists:artist_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    return obj


@router.delete(
    '/{int:artist_id}',
    response={204: None},
    auth=ARTIST_AUTH['DELETE'],
    description="Delete an artist by ID and clear associated cache."
)
async def delete_artist(
    request,
    artist_id: int,
):
    """
    Deletes an artist.

    - Deletes the image file associated with the artist.
    - Removes the artist from cache and database.
    - Returns HTTP 204 (no content) on success.
    """
    obj = await aget_object_or_404(Artist, pk=artist_id)
    key = f"artists:artist_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    await obj.adelete()

    return 204, None
