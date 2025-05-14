from ninja import Router, Form, File, UploadedFile, Query
from django.conf import settings
from django.db.models import Count
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django.shortcuts import aget_object_or_404
from ninja.errors import ValidationError
from ninja.pagination import paginate
from asgiref.sync import sync_to_async

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
    errors = []
    try:
        artist = Artist(**form.dict(exclude_unset=True))
        # Validate the image if provided
        if image:
            if utils.validate_image(image):
                artist.image = image
            else:
                err = utils.make_error(
                    ['form'], 'image', _('File is not an image')
                )
                errors.append(err)

    except IntegrityError:
        errors.append(
            utils.make_errors(['form'], 'name', _('Artist already exists'))
        )

    if errors:
        raise ValidationError(errors)
    else:
        await artist.asave()
        return 201, artist


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
    qs = Artist.objects.annotate(
        song_count=Count('songs'),
        album_count=Count('albums')
    )
    return await sync_to_async(list)(filters.filter(qs))


@router.get(
    '/{int:artist_id}',
    response=SingleArtistSchemaOut,
    auth=settings.TAGTRACK_AUTH['READ']
)
async def get_artist(request, artist_id: int):
    qs = Artist.objects.annotate(
        song_count=Count('songs'),
        album_count=Count('albums')
    ).prefetch_related('songs', 'albums')
    return await aget_object_or_404(qs, pk=artist_id)


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
    obj, created = await Artist.objects.aget_or_create(**data)

    # Set new image
    if image and utils.validate_image(image):
        await sync_to_async(obj.image.save)(image.name, image)

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

    obj.image.delete(save=False)
    await obj.adelete()

    return obj
