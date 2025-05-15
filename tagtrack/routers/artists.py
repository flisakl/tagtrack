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
    auth=settings.TAGTRACK_AUTH['CREATE']
)
async def create_artist(
    request,
    form: Form[ArtistSchemaIn],
    image: UploadedFile | None = File(None)
):
    artist = Artist(**form.dict(exclude_unset=True))

    # Validate the image if provided
    if image:
        if utils.validate_image(image):
            artist.image = image
        else:
            err = utils.make_error(
                ['form'], 'image', _('File is not an image')
            )
            raise ValidationError([err])

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
    auth=settings.TAGTRACK_AUTH['READ']
)
@paginate
async def get_artists(
    request,
    filters: Query[ArtistFilterSchema]
):
    key = f"artists:{urlencode(request.GET, doseq=True)}"
    qs = filters.filter(Artist.objects.annotate(
        song_count=Count('songs'),
        album_count=Count('albums')
    ))
    return await utils.get_or_set_from_cache(key, qs)


@router.get(
    '/{int:artist_id}',
    response=SingleArtistSchemaOut,
    auth=settings.TAGTRACK_AUTH['READ']
)
async def get_artist(request, artist_id: int):
    key = f"artists:artist_id={artist_id}"
    qs = Artist.objects.annotate(
        song_count=Count('songs'),
        album_count=Count('albums')
    ).prefetch_related('songs__album', 'albums')
    obj = await utils.get_or_set_from_cache(key, qs, artist_id)

    for song in obj.songs.all():
        sa = song.album
        if sa:
            song.image = sa.image
            song.genre = song.genre if song.genre else sa.genre
            song.year = song.year if song.year else sa.year
    return obj


@router.patch(
    '/{int:artist_id}',
    response=ArtistSchemaOut,
    auth=settings.TAGTRACK_AUTH['UPDATE']
)
async def update_artist(
    request,
    artist_id: int,
    form: Form[ArtistSchemaIn],
    image: UploadedFile | None = File(None)
):
    data = form.dict(exclude_unset=True)
    obj = await aget_object_or_404(Artist, pk=artist_id)

    for attr, value in data.items():
        setattr(obj, attr, value)

    # Set new image
    if image and utils.validate_image(image):
        await sync_to_async(obj.image.save)(image.name, image, save=False)

    try:
        await obj.asave()
    except IntegrityError:
        raise ValidationError([
            utils.make_error(['form'], 'name', _('Artist already exists'))
        ])

    # Remove item from cache
    key = f"artists:artist_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    return obj


@router.delete(
    '/{int:artist_id}',
    response={204: None},
    auth=settings.TAGTRACK_AUTH['DELETE']
)
async def delete_artist(
    request,
    artist_id: int,
):
    obj = await aget_object_or_404(Artist, pk=artist_id)
    # Remove item from cache
    key = f"artists:artist_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    obj.image.delete(save=False)
    await obj.adelete()

    return obj
