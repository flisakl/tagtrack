from ninja import Router, Form, File, UploadedFile, Query
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django.shortcuts import aget_object_or_404
from ninja.errors import ValidationError
from ninja.pagination import paginate
from asgiref.sync import sync_to_async
from urllib.parse import urlencode

from tagtrack import utils
from tagtrack.models import Artist
from .schemas import (
    ArtistSchemaIn, ArtistSchemaOut, ArtistFilterSchema, SingleArtistSchemaOut
)

router = Router(tags=["Artists"])


@router.post(
    '',
    response={201: ArtistSchemaOut},
    auth=settings.TAGTRACK_AUTH['CREATE'],
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

    if err := await utils.validate_image(image):
        raise err
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
    auth=settings.TAGTRACK_AUTH['READ'],
    description="Retrieve a paginated list of artists with optional filtering."
)
@paginate
async def get_artists(
    request,
    filters: Query[ArtistFilterSchema]
):
    """
    Retrieves a paginated list of artists.

    - Supports filtering through query parameters.
    - Annotates artist entries with counts of related songs and albums.
    - Results are cached by querystring.
    """
    key = f"artists:{urlencode(sorted(request.GET.items()), doseq=True)}"
    qs = filters.filter(Artist.objects.annotate(
        song_count=Count('songs'),
        album_count=Count('albums')
    ))
    return await utils.get_or_set_from_cache(key, qs)


@router.get(
    '/{int:artist_id}',
    response=SingleArtistSchemaOut,
    auth=settings.TAGTRACK_AUTH['READ'],
    description="Retrieve details for a specific artist by ID."
)
async def get_artist(request, artist_id: int):
    """
    Retrieves detailed information about a specific artist.

    - Annotates artist with song and album counts.
    - Prefetches songs and related albums.
    - Caches the response by artist ID.
    """
    key = f"artists:artist_id={artist_id}"
    qs = Artist.objects.annotate(
        song_count=Count('songs'),
        album_count=Count('albums')
    ).prefetch_related('songs__album', 'albums')
    obj = await utils.get_or_set_from_cache(key, qs, artist_id)

    for song in obj.songs.all():
        if song.album:
            utils.fill_song_fields(song, song.album)
    return obj


@router.patch(
    '/{int:artist_id}',
    response=ArtistSchemaOut,
    auth=settings.TAGTRACK_AUTH['UPDATE'],
    description="Update an existing artist by ID, including optional image replacement."
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

    if image and not await utils.validate_image(image):
        obj.image.delete(save=False)
        obj.image.save(image.name, image, save=False)

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
    auth=settings.TAGTRACK_AUTH['DELETE'],
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
