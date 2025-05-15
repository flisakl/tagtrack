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
from tagtrack.models import Album, Artist
from .schemas import (
    AlbumSchemaIn, AlbumSchemaOut, AlbumFilterSchema, SingleAlbumSchemaOut
)

router = Router(tags=["Albums"])


@router.post(
    '',
    response={201: AlbumSchemaOut},
    auth=settings.TAGTRACK_AUTH['CREATE']
)
async def create_album(
    request,
    form: Form[AlbumSchemaIn],
    image: UploadedFile | None = File(None)
):
    album = Album(**form.dict(exclude_unset=True))
    try:
        await Artist.objects.aget(pk=form.artist_id)
    except Artist.DoesNotExist:
        raise ValidationError([
            utils.make_error(['form'], 'name', _('Artist does not exist'))
        ])

    if image:
        if not utils.validate_image(image):
            err = utils.make_error(
                ['form'], 'image', _('File is not an image')
            )
            raise ValidationError(
                [err]
            )
        else:
            album.image = image
    try:
        await album.asave()

    except IntegrityError as e:
        if 'unique' in str(e).lower():
            err = utils.make_error(
                ['form'], 'artist_id', _('Album already exists')
            )
            raise ValidationError([err])
    # Update cache
    key = f"albums:album_id={album.pk}"
    await sync_to_async(cache.set)(key, album)
    return 201, album
