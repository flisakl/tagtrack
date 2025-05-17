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
    if image:
        if err := utils.validate_image(image):
            raise err
        album.image = image
    try:
        album.artist = await Artist.objects.aget(pk=form.artist_id)
        await album.asave()
        return 201, album
    except IntegrityError:
        err = utils.make_error(
            ['form'], 'name', _('Album already exists')
        )
        raise ValidationError([err])
    except Artist.DoesNotExist:
        err = utils.make_error(
            ['form'], 'artist_id', _('Artist does not exist')
        )
        raise ValidationError([err])


@router.get(
    '',
    response=list[AlbumSchemaOut],
    auth=settings.TAGTRACK_AUTH['READ']
)
@paginate
async def get_albums(
    request,
    filters: Query[AlbumFilterSchema]
):
    key = f"albums:{urlencode(request.GET, doseq=True)}"
    qs = filters.filter(Album.objects.annotate(
        song_count=Count('songs'),
        total_duration=Sum('songs__duration') / 60
    ))
    return await utils.get_or_set_from_cache(key, qs)


@router.get(
    '/{int:album_id}',
    response=SingleAlbumSchemaOut,
    auth=settings.TAGTRACK_AUTH['READ']
)
async def get_album(request, album_id: int):
    key = f"albums:album_id={album_id}"
    qs = Album.objects.annotate(
        song_count=Count('songs'),
        total_duration=Sum('songs__duration') / 60
    ).select_related('artist').prefetch_related('songs')
    obj = await utils.get_or_set_from_cache(key, qs, album_id)

    for song in obj.songs.all():
        utils.fill_song_fields(song, obj)
    return obj


@router.patch(
    '/{int:album_id}',
    response=AlbumSchemaOut,
    auth=settings.TAGTRACK_AUTH['UPDATE']
)
async def update_album(
    request,
    album_id: int,
    form: Form[AlbumSchemaIn],
    image: UploadedFile | None = File(None)
):
    data = form.dict(exclude_unset=True)
    try:
        obj = await aget_object_or_404(Album, pk=album_id)
        obj.artist = await Artist.objects.aget(pk=form.artist_id)
        if image and not utils.validate_image(image):
            obj.image.delete(save=False)
            obj.image.save(image.name, image, save=False)

        for attr, value in data.items():
            setattr(obj, attr, value)
        await obj.asave()
    except IntegrityError:
        err = utils.make_error(['form'], 'name', _('Album already exists'))
        raise ValidationError([err])
    except Artist.DoesNotExist:
        raise ValidationError([
            utils.make_error(['form'], 'artist_id', _('Artist does not exist'))
        ])
    key = f"albums:album_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    return obj


@router.delete(
    '/{int:album_id}',
    response={204: None},
    auth=settings.TAGTRACK_AUTH['DELETE']
)
async def delete_album(
    request,
    album_id: int,
):
    obj = await aget_object_or_404(Album, pk=album_id)
    # Update cache
    key = f"albums:album_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    await obj.adelete()

    return obj
