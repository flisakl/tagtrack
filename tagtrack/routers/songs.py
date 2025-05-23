from ninja import Router, Form, File, UploadedFile, Query
from django.utils.translation import gettext_lazy as _
from django.shortcuts import aget_object_or_404
from django.core.cache import cache
from ninja.errors import ValidationError
from ninja.pagination import paginate
from asgiref.sync import sync_to_async
from urllib.parse import urlencode
from django.http import FileResponse

from tagtrack import utils, tags
from tagtrack.models import Album, Artist, Song
from .schemas import (
    SongSchemaIn, SongSchemaOut, SingleSongSchemaOut, SongFilterSchema,
    UploadSchemaOut
)
from tagtrack import SONG_AUTH, MAX_SONG_DOWNLOAD

router = Router(tags=["Songs"])


@router.post(
    '',
    response={201: SingleSongSchemaOut},
    auth=SONG_AUTH['CREATE'],
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
    artist_ids = data.pop('artist_ids', [])
    song = Song(**data)

    if album:
        if not await Album.objects.filter(pk=album).aexists():
            raise ValidationError([
                utils.make_error(['form'], 'album_id',
                                 _('Album does not exist'))
            ])
        song.album_id = album

    if err := await utils.validate_audio_file(file):
        raise err
    song.file = file

    if err := await utils.validate_image(image):
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
    auth=SONG_AUTH['READ'],
    description="Retrieve a paginated list of songs with filtering support. Includes related album info.",
    exclude_unset=True
)
@paginate
async def get_songs(
    request,
    filters: Query[SongFilterSchema]
):
    """
    Returns a paginated list of songs, filtered using query parameters.
    Each song includes its album information.
    Results are cached per querystring.
    """
    key = f"songs:{urlencode(sorted(request.GET.items()), doseq=True)}"
    qs = filters.filter(Song.objects.select_related('album'))
    result = await utils.get_or_set_from_cache(key, qs)
    for song in result:
        utils.fill_song_fields(song, song.album)
    return result


@router.get(
    '/{int:song_id}',
    response=SingleSongSchemaOut,
    auth=SONG_AUTH['READ'],
    description="Retrieve a single song by ID. Includes related album and artists.",
    exclude_unset=True
)
async def get_song(request, song_id: int):
    """
    Retrieves full details for a single song, including album and artists.
    Uses cache when available.
    """
    key = f"songs:song_id={song_id}"
    qs = Song.objects.select_related('album').prefetch_related('artists')
    song = await utils.get_or_set_from_cache(key, qs, song_id)
    utils.fill_song_fields(song, song.album)
    return song


@router.patch(
    '/{int:song_id}',
    response={200: SingleSongSchemaOut},
    auth=SONG_AUTH['UPDATE'],
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
    artist_ids = data.pop('artist_ids', [])

    song = await aget_object_or_404(Song, pk=song_id)

    if album:
        if not await Album.objects.filter(pk=album).aexists():
            raise ValidationError([
                utils.make_error(['form'], 'album_id',
                                 _('Album does not exist'))
            ])
        song.album_id = album

    if file and not await utils.validate_audio_file(file):
        await sync_to_async(song.file.delete)(save=False)
        await sync_to_async(song.file.save)(file.name, file, save=False)

    if image and not await utils.validate_image(image):
        await sync_to_async(song.image.delete)(save=False)
        await sync_to_async(song.image.save)(image.name, image, save=False)

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
    auth=SONG_AUTH['DELETE'],
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


@router.post(
    '/upload',
    response=UploadSchemaOut,
    auth=SONG_AUTH['CREATE'],
    description="""
    Upload multiple audio files, extract metadata (title, artist, album, genre),
    and populate the database with any new songs, albums, or artists. Also handles
    untagged or invalid files gracefully.
    """
)
async def upload_files(
    request,
    files: list[UploadedFile] = File([])
):

    info = await extract_metadata(files)
    albums = info['albums']
    artists = info['artists']
    songs = info['songs']
    untagged_files = info['untagged']
    res = info['stats']
    songs_with_album = [s for s in songs if s['album']]
    album_song_map = {
        a: [s for s in songs_with_album if s['album'] == s]
        for a in albums.keys()
    }

    # Set album genres to most occuring song genre
    for name, data in albums.items():
        gcount = {}
        asongs = album_song_map.get(name)
        for song in asongs:
            g = song['instance'].genre
            gcount[g] = gcount.get(g, 0) + 1
        maxval = 0
        key = None
        for genre, count in gcount.items():
            if count > maxval:
                key = genre
                maxval = count
        data['genre'] = key

    db_artists, db_albums = await fetch_or_create_albums_and_artists(
        albums, artists
    )

    await create_songs(songs, db_artists, db_albums)
    untagged_songs = []
    for uf in untagged_files:
        untagged_songs.append(
            Song(
                file=uf,
                name='Unnamed',
                duration=0
            )
        )

    await Song.objects.abulk_create(untagged_songs)

    return res


async def add_artists_from_metadata(
    metadata: dict,
    artists: dict
) -> list[dict]:
    """
    Extracts and adds artist metadata to the global artist collection.

    If the album has a separate artist, it is also added to the artist list.
    Ensures that image data from APIC frames is cached as a temporary file.

    Args:
        metadata (dict): Song metadata parsed from file.
        artists (dict): Current dictionary of known artist data.

    Returns:
        list[dict]: List of artist data entries used for this song.
    """
    ret = []
    if metadata['album'] and metadata['album']['artist']:
        metadata['artists'].append(metadata['album']['artist'])
    for art in metadata['artists']:
        im = await utils.make_tempfile_from_apic_frame(art['image'])
        key = art['name']
        if key not in artists.keys():
            artists[key] = {'data': art}
            artists[key]['data']['image'] = im
        elif im and not artists[key]['data'].get('image'):
            artists[key]['data']['image'] = im
        ret.append(artists[key])

    return ret


async def add_album_from_metadata(
    metadata: dict,
    albums: dict
) -> dict | None:
    """
    Extracts and adds album metadata to the global album collection.

    Associates the album with the correct artist if present. Caches the album
    image using a temporary file from APIC frame.

    Args:
        metadata (dict): Song metadata parsed from file.
        albums (dict): Current dictionary of known album data.

    Returns:
        dict | None: Album data entry if album metadata is available, else None.
    """

    if metadata['album']:
        im = await utils.make_tempfile_from_apic_frame(metadata['album']['image'])
        aa = metadata['album']['artist']

        key = (metadata['album']['name'], aa['name'] if aa else None)

        if key not in albums.keys():
            albums[key] = {'data': metadata['album']}
            albums[key]['data']['image'] = im
        if im and not albums[key].get('image'):
            albums[key]['data']['image'] = im
        return albums[key]
    return None


async def add_song_from_metadata(
    metadata: dict,
    songs: list,
    artists: list[dict],
    album: dict | None,
    file: UploadedFile
):
    """
    Constructs a Song instance from parsed metadata and adds it to the songs list.

    Args:
        metadata (dict): Song metadata from ID3/APIC tags.
        songs (list): Accumulated list of songs to upload.
        artists (list[dict]): Artist data used in the song.
        album (dict | None): Album data if available.
        file (UploadedFile): The uploaded audio file.
    """

    im = await utils.make_tempfile_from_apic_frame(metadata['image'])
    s = Song(
        name=metadata['name'],
        year=metadata['year'],
        genre=metadata['genre'],
        duration=metadata['duration'],
        number=metadata['number'],
        image=im,
        file=file
    )
    songs.append({
        'instance': s,
        'artists': [x['data']['name'] for x in artists],
        'album': album['data']['name'] if album else None
    })


async def extract_metadata(files: list[UploadedFile]) -> dict:
    """
    Extracts song, artist, and album metadata from uploaded audio files.

    Separates untagged and invalid files, builds metadata collections, and prepares
    stats for the upload response.

    Args:
        files (list[UploadedFile]): List of uploaded audio files.

    Returns:
        dict: Metadata collections and statistics:
            - 'songs': list of extracted song data
            - 'albums': dict of album metadata
            - 'artists': dict of artist metadata
            - 'untagged': list of files with no tags
            - 'stats': summary of total, invalid, and untagged files
    """
    stats = {
        'total_count': len(files),
        'invalid_files': []
    }
    artists = {}
    albums = {}
    songs = []
    untagged_files = []

    for file in files:
        if not await utils.validate_audio_file(file):
            meta = await tags.read_metadata(file)
            if meta:
                song_artists = await add_artists_from_metadata(meta, artists)
                song_album = await add_album_from_metadata(meta, albums)
                await add_song_from_metadata(
                    meta, songs, song_artists, song_album, file
                )
            else:
                untagged_files.append(file)
        else:
            stats['invalid_files'].append(file.name)

    stats['invalid_count'] = len(stats['invalid_files'])

    return {
        'stats': stats,
        'albums': albums,
        'songs': songs,
        'artists': artists,
        'untagged': untagged_files
    }


async def fetch_or_create_albums_and_artists(
    albums: dict,
    artists: dict
) -> tuple[list[Artist], list[Album]]:
    """
    Ensures all referenced albums and artists exist in the database.

    - Fetches existing albums and artists by name.
    - Creates new Album and Artist entries for any missing ones.
    - Returns two lists of DB model instances: (artists, albums).

    Args:
        albums (dict): Extracted album metadata keyed by (album_name, artist_name).
        artists (dict): Extracted artist metadata keyed by artist name.

    Returns:
        tuple: (list[Artist], list[Album])
    """

    # Fetch all artists and create missing ones
    db_artists = await sync_to_async(list)(Artist.objects.filter(name__in=artists.keys()))
    db_artists_names = [a.name for a in db_artists]
    artist_to_create = []
    for artist_name in artists.keys():
        if artist_name not in db_artists_names:
            artist_to_create.append(Artist(**artists[artist_name]['data']))
    db_artists.extend(await Artist.objects.abulk_create(artist_to_create))
    artist_map = {a.name: a for a in db_artists}

    # Fetch all albums and create missing ones
    qs = Album.objects.select_related(
        'artist'
    ).filter(name__in=[x[0] for x in albums.keys()])
    db_albums = await sync_to_async(list)(qs)
    db_albums_names = [a.name for a in db_albums]
    album_to_create = []
    for combined_key in albums.keys():
        album_name = combined_key[0]
        artist_name = combined_key[1]
        if album_name not in db_albums_names:
            data = albums[combined_key]['data']
            # Attach artist to album
            if data['artist']:
                data['artist'] = artist_map.get(artist_name)
            album_to_create.append(Album(**data))
    db_albums.extend(await Album.objects.abulk_create(album_to_create))

    return db_artists, db_albums


async def create_songs(
    songs: list,
    db_artists: list[Artist],
    db_albums: list[Album]
):
    """
        Creates new Song records and associates them with Albums and Artists.

        Ensures no duplicate songs are created by checking for:
        - Matching name
        - Matching album
        - Matching artist set

        Bulk inserts songs and links artists through the many-to-many relationship.

        Args:
            songs (list): Parsed song data with metadata.
            db_artists (list[Artist]): List of Artist model instances.
            db_albums (list[Album]): List of Album model instances.
    """
    song_names = [x['instance'].name for x in songs]
    qs = Song.objects.prefetch_related(
        'artists'
    ).select_related('album').filter(name__in=song_names)
    db_songs = await sync_to_async(list)(qs)
    songs_to_create = []
    SongArtist = Song.artists.through
    song_artist_instances = []

    # Quick access
    artist_map = {a.name: a for a in db_artists}
    album_map = {
        (
            alb.name,
            alb.artist.name if alb.artist else None
        ): alb for alb in db_albums}
    song_map = {(
        s.name,
        s.album.name if s.album else None,
        frozenset([a.name for a in s.artists.all()])
    ): s for s in db_songs}

    for song in songs:
        inst = song['instance']
        song_artists = frozenset(song['artists'])
        artist_instances = []
        # Skip adding songs with matching name, album and artists
        skip = song_map.get((inst.name, song['album'], song_artists), False)
        if skip:
            continue

        # Attach album instance
        if song['album']:
            for sa in song_artists:
                if art := album_map.get((song['album'], sa)):
                    inst.album = art
                    break
        # Switch artist dictionaries to artist instances
        for sa in song_artists:
            art = artist_map.get(sa)
            if art:
                artist_instances.append(art)
        # WARN notice that now we're storing instances of Artist model
        song['artists'] = artist_instances

        songs_to_create.append(song)

    song_instances = [x['instance'] for x in songs_to_create]
    await Song.objects.abulk_create(song_instances)
    # Attach artists to created songs
    for song in songs_to_create:
        for art in song['artists']:
            song_artist_instances.append(
                SongArtist(song=song['instance'], artist=art)
            )
    await SongArtist.objects.abulk_create(song_artist_instances)


@router.get(
    '/download',
    auth=SONG_AUTH['DOWNLOAD'],
    response={404: dict}
)
async def download_songs(
    request,
    song_ids: Query[list[int]],
):
    if (len(song_ids) > MAX_SONG_DOWNLOAD):
        err = {
            'loc': ['query', 'song_ids'],
            'msg': _('Requested too many files')
        }
        return 422, {'detail': [err]}
    qs = Song.objects.prefetch_related('artists').select_related(
        'album__artist').filter(pk__in=song_ids)
    songs = await sync_to_async(list)(qs)
    for song in songs:
        if song.retag:
            await tags.write_metadata(song)

    if len(songs) > 1:
        zipfile = await utils.make_zip_file(songs)
        return utils.CloseFileResponse(
            zipfile, as_attachment=True, filename='songs.zip')
    elif len(songs) == 1:
        return FileResponse(
            songs[0].file, as_attachment=True
        )

    return 404, {'detail': _('Not Found: No songs found')}
