from ninja import Router, Form, File, UploadedFile, Query
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.shortcuts import aget_object_or_404
from django.core.cache import cache
from ninja.errors import ValidationError
from ninja.pagination import paginate
from asgiref.sync import sync_to_async
from urllib.parse import urlencode

from tagtrack import utils
from tagtrack.models import Album, Artist, Song
from .schemas import (
    SongSchemaIn, SongSchemaOut, SingleSongSchemaOut, SongFilterSchema,
)

router = Router(tags=["Songs"])


@router.post(
    '',
    response={201: SingleSongSchemaOut},
    auth=settings.TAGTRACK_AUTH['CREATE'],
    description="Create a new song with required audio file and optional image. Assigns to album and artists if provided."
)
async def create_song(
    request,
    form: Form[SongSchemaIn],
    file: File[UploadedFile],
    image: UploadedFile | None = File(None),
):
    """
    Creates a new song with metadata from form data, an audio file (required),
    and an optional image. If `album_id` is provided, verifies album existence.
    Associates the song with provided artists.
    Returns HTTP 201 with the full song representation on success.
    """
    data = form.dict(exclude_unset=True)
    album = data.pop('album_id', None)
    artist_ids = data.pop('artist_ids', None)
    artist_ids = [int(x) for x in artist_ids.split(',')] if artist_ids else []
    song = Song(**data)

    if album:
        if not await Album.objects.filter(pk=album).aexists():
            raise ValidationError([
                utils.make_error(['form'], 'album_id', _('Album does not exist'))
            ])
        song.album_id = album

    if err := utils.validate_audio_file(file):
        raise err
    song.file = file

    if err := utils.validate_image(image):
        raise err
    song.image = image

    await song.asave()

    qs = Artist.objects.filter(pk__in=artist_ids)
    artists = await sync_to_async(list)(qs)
    await song.artists.aadd(*artists)

    obj = await Song.objects.prefetch_related('artists').select_related('album').aget(pk=song.pk)
    return 201, obj


@router.get(
    '',
    response=list[SongSchemaOut],
    auth=settings.TAGTRACK_AUTH['READ'],
    description="Retrieve a paginated list of songs with filtering support. Includes related album info."
)
@paginate
async def get_albums(
    request,
    filters: Query[SongFilterSchema]
):
    """
    Returns a paginated list of songs, filtered using query parameters.
    Each song includes its album information.
    Results are cached per querystring.
    """
    key = f"songs:{urlencode(request.GET, doseq=True)}"
    qs = filters.filter(Song.objects.select_related('album'))
    return await utils.get_or_set_from_cache(key, qs)


@router.get(
    '/{int:song_id}',
    response=SingleSongSchemaOut,
    auth=settings.TAGTRACK_AUTH['READ'],
    description="Retrieve a single song by ID. Includes related album and artists."
)
async def get_song(request, song_id: int):
    """
    Retrieves full details for a single song, including album and artists.
    Uses cache when available.
    """
    key = f"songs:song_id={song_id}"
    qs = Song.objects.select_related('album').prefetch_related('artists')
    return await utils.get_or_set_from_cache(key, qs, song_id)


@router.patch(
    '/{int:song_id}',
    response={200: SingleSongSchemaOut},
    auth=settings.TAGTRACK_AUTH['UPDATE'],
    description="Update song metadata. Supports updating audio and image files, artist associations, and album."
)
async def update_song(
    request,
    song_id: int,
    form: Form[SongSchemaIn],
    file: UploadedFile | None = File(None),
    image: UploadedFile | None = File(None),
):
    """
    Updates metadata and associations for an existing song.
    - If a new audio file is provided, replaces the existing one.
    - If a new image is provided, replaces the existing one.
    - Updates artist associations and album reference.
    Clears the cache for the updated song.
    """
    data = form.dict(exclude_unset=True)
    album = data.pop('album_id', None)
    artist_ids = data.pop('artist_ids', None)
    artist_ids = [int(x) for x in artist_ids.split(',')] if artist_ids else []

    song = await aget_object_or_404(Song, pk=song_id)

    if album:
        if not await Album.objects.filter(pk=album).aexists():
            raise ValidationError([
                utils.make_error(['form'], 'album_id', _('Album does not exist'))
            ])
        song.album_id = album

    if file and not utils.validate_audio_file(file):
        song.file.delete(save=False)
        song.file.save(file.name, file, save=False)

    if image and not utils.validate_image(image):
        song.image.delete(save=False)
        song.image.save(image.name, image, save=False)

    for k, v in data.items():
        setattr(song, k, v)

    await song.asave()

    qs = Artist.objects.filter(pk__in=artist_ids)
    artists = await sync_to_async(list)(qs)
    await song.artists.aset(artists)

    obj = await Song.objects.prefetch_related('artists').select_related('album').aget(pk=song.pk)

    # Invalidate cache
    key = f"songs:song_id={obj.pk}"
    await sync_to_async(cache.delete)(key)

    return obj


@router.delete(
    '/{int:song_id}',
    response={204: None},
    auth=settings.TAGTRACK_AUTH['DELETE'],
    description="Delete a song by ID. Removes cache and file attachments."
)
async def delete_song(
    request,
    song_id: int,
):
    """
    Deletes the specified song from the database.
    Removes associated files and invalidates cache entry.
    Returns HTTP 204 on success.
    """
    obj = await aget_object_or_404(Song, pk=song_id)
    key = f"songs:song_id={obj.pk}"
    await sync_to_async(cache.delete)(key)
    await obj.adelete()
    return 204, None
