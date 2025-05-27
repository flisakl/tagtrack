from ninja import Router, Form, File, UploadedFile, Query
from django.core.cache import cache
from django.db.models import Count, Sum
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django.shortcuts import aget_object_or_404
from ninja.errors import ValidationError
from ninja.pagination import paginate
from asgiref.sync import sync_to_async
from urllib.parse import urlencode

from tagtrack import ALBUM_AUTH
from tagtrack import utils, tags
from tagtrack.models import Album, Artist, Song
from .schemas import (
    AlbumSchemaIn, AlbumSchemaOut, AlbumFilterSchema, SingleAlbumSchemaOut,
    AlbumWithArtistSchemaOut
)

router = Router(tags=["Albums"])


@router.post(
    '',
    response={201: AlbumSchemaOut},
    auth=ALBUM_AUTH['CREATE'],
    description="Create a new album with optional cover image. Requires a valid artist ID."
)
async def create_album(
    request,
    form: Form[AlbumSchemaIn],
    image: UploadedFile | None = File(None)
):
    """
    Creates a new album. If a cover image is provided, it is validated and attached.
    Returns HTTP 201 with the created album or raises a ValidationError if the album name
    already exists or artist is not found.
    """
    album = Album(**form.dict(exclude_unset=True))
    await sync_to_async(utils.raise_on_invalid_image)(image)
    album.image = image
    try:
        album.artist = await Artist.objects.aget(pk=form.artist_id)
        await album.asave()
        return 201, album
    except IntegrityError:
        err = utils.make_error(['form'], 'name', _('Album already exists'))
        raise ValidationError([err])
    except Artist.DoesNotExist:
        err = utils.make_error(['form'], 'artist_id',
                               _('Artist does not exist'))
        raise ValidationError([err])


@router.get(
    '',
    response=list[AlbumWithArtistSchemaOut],
    auth=ALBUM_AUTH['READ'],
    description="List albums with filtering and pagination. Includes song count and total duration in minutes.",
    exclude_unset=True,
    exclude_none=True
)
@paginate
async def get_albums(
    request,
    filters: Query[AlbumFilterSchema]
):
    """
    Returns a paginated list of albums, filtered according to query parameters.
    Each album includes the number of songs and total duration (in minutes).
    Results are cached based on the querystring.
    """
    key = f"albums:{urlencode(sorted(request.GET.items()), doseq=True)}"
    qs = Album.objects.annotate(
        song_count=Count('songs'),
        total_duration=Sum('songs__duration') / 60).select_related('artist')
    qs = filters.filter(qs)
    return await utils.get_or_set_from_cache(key, qs)


@router.get(
    '/{int:album_id}',
    response=SingleAlbumSchemaOut,
    auth=ALBUM_AUTH['READ'],
    description="Retrieve a single album by ID, including related songs and artist.",
    exclude_unset=True,
    exclude_none=True
)
async def get_album(request, album_id: int):
    """
    Returns detailed information about a single album, including all songs and their metadata.
    Annotates song count and total duration. Uses caching.
    """
    key = f"albums:album_id={album_id}"
    qs = Album.objects.annotate(
        song_count=Count('songs'),
        total_duration=Sum('songs__duration') / 60
    ).select_related('artist').prefetch_related('songs__artists')
    obj = await utils.get_or_set_from_cache(key, qs, album_id)

    for song in obj.songs.all():
        utils.fill_song_fields(song, obj)
    return obj


@router.patch(
    '/{int:album_id}',
    response=AlbumSchemaOut,
    auth=ALBUM_AUTH['UPDATE'],
    description="Update an existing album's details and optionally replace its image."
)
async def update_album(
    request,
    album_id: int,
    form: Form[AlbumSchemaIn],
    image: UploadedFile | None = File(None)
):
    """
    Updates an existing album. If a new image is provided, it replaces the old one.
    Also checks for artist existence and ensures name uniqueness.
    Clears the cached data for the album.
    """
    data = form.dict(exclude_unset=True)
    try:
        obj = await aget_object_or_404(Album, pk=album_id)
        obj.artist = await Artist.objects.aget(pk=form.artist_id)
        if image:
            await sync_to_async(utils.raise_on_invalid_image)(image)
            await sync_to_async(obj.image.delete)(save=False)
            await sync_to_async(obj.image.save)(image.name, image, save=False)

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
    auth=ALBUM_AUTH['DELETE'],
    description="Delete an album by ID. Also clears cache and deletes associated image."
)
async def delete_album(
    request,
    album_id: int,
):
    """
    Deletes the album with the given ID from the database.
    Also removes any associated image file and clears the corresponding cache key.
    Returns HTTP 204 on success.
    """
    obj = await aget_object_or_404(Album, pk=album_id)
    key = f"albums:album_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    await obj.adelete()
    return 204, None


@router.get(
    '{int:album_id}/download',
    auth=ALBUM_AUTH['DOWNLOAD'],
    response={404: dict}
)
async def download_album(request, album_id: int):
    qs = Song.objects.prefetch_related('artists').select_related(
        'album__artist').filter(album_id=album_id)
    songs = await sync_to_async(list)(qs)
    for song in songs:
        if song.retag:
            await tags.write_metadata(song)

    if len(songs):
        zipfile = await utils.make_zip_file(songs)
        res = utils.CloseFileResponse(
            zipfile, as_attachment=True, filename='songs.zip')
        return res
    return 404, {'detail': _('Not Found: No songs found')}
