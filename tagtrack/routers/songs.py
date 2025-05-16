from ninja import Router, Form, File, UploadedFile, Query
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Sum
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django.shortcuts import aget_object_or_404
from ninja.errors import ValidationError
from ninja.pagination import paginate
from asgiref.sync import sync_to_async
from urllib.parse import urlencode

from tagtrack import utils
from tagtrack.models import Album, Artist, Song
from .schemas import (
    SongSchemaIn, SongSchemaOut, SingleSongSchemaOut
)

router = Router(tags=["Songs"])


@router.post(
    '',
    response={201: SingleSongSchemaOut},
    auth=settings.TAGTRACK_AUTH['CREATE']
)
async def create_song(
    request,
    form: Form[SongSchemaIn],
    file: File[UploadedFile],
    image: UploadedFile | None = File(None),
):
    data = form.dict(exclude_unset=True)
    album = data.pop('album_id', None)
    artist_ids = data.pop('artist_ids', None)
    artist_ids = [int(x) for x in artist_ids.split(',')] if artist_ids else []
    song = Song(**data)

    if album:
        if not await Album.objects.filter(pk=album).aexists():
            raise ValidationError([
                utils.make_error(
                    ['form'], 'album_id', _('Album does not exist')
                )
            ])
        song.album_id = album

    if err := utils.validate_audio_file(file):
        raise err
    else:
        song.file = file

    if image:
        if err := utils.validate_image(image):
            raise err
        song.image = image

    await song.asave()
    qs = Artist.objects.filter(pk__in=artist_ids)
    artists = await sync_to_async(list)(qs)
    await song.artists.aadd(*artists)
    obj = await Song.objects.prefetch_related('artists').select_related(
        'album').aget(pk=song.pk)
    return 201, obj
