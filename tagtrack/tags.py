from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db.models.fields.files import FieldFile
from mutagen import File, FileType, Tags
from mutagen.id3 import ID3FileType, PictureType, ID3
from mutagen.id3 import APIC, TPE1, TPE2, TALB, TIT2, TDRC, TCON, TRCK
from mutagen._constants import GENRES
from mutagen.mp4 import MP4, MP4Cover
import os

from tagtrack.utils import image_is_valid
from .models import Song
from typing import Callable
import mimetypes


class Editor:
    def __init__(self):
        self.tags: Tags
        self.meta: dict

    def read(self, file: FileType) -> dict[str, any]:
        raise NotImplementedError()

    def write(
        self,
        file: FieldFile,
        metadata: dict[str, any],
        song: Song = None
    ) -> None:
        raise NotImplementedError()

    def _genre_is_valid(self, genre: str):
        return genre and genre in GENRES

    def _set_if_present(
        self,
        key: str,
        value: any,
        d: dict = None
    ):
        if value:
            if d:
                d[key] = value
            else:
                self.meta[key] = value

    def song_to_metadata(self, song: Song) -> None:
        self.meta = {
            # These fields have default values
            'name': song.name,
            'number': song.number,
            'year': song.year
        }
        if self._genre_is_valid(song.genre):
            self.meta['genre'] = song.genre
        self._set_if_present("image", song.image)

        # If album exists, it means that album artist is also available
        if album := song.album:
            alb = {
                'name': album.name,
                'artist': album.artist.name,
            }
            self._set_if_present("image", album.image, alb)
            self.meta['album'] = alb

        artists = []
        for art in song.artists.all():
            data = {
                'name': art.name,
            }
            self._set_if_present("image", art.image, data)
            artists.append(data)
        self.meta['artists'] = artists


def _process_id3_year(value: str) -> int:
    return int(str(value)[:4])


def _process_id3_track(value: str) -> int:
    return int(value.split('/')[0])


class ID3Editor(Editor):

    def _read_tag(
        self,
        tagname: str,
        key_to_set: str,
        dict_to_set: dict = None,
        value_processing_func: Callable = None,
    ):
        dts = dict_to_set if dict_to_set is not None else self.meta
        if tvalue := self.tags.get(tagname):
            tvalue = tvalue.text[0]
            if value_processing_func:
                dts[key_to_set] = value_processing_func(tvalue)
            else:
                dts[key_to_set] = tvalue

    def _make_apic_frame(
        self,
        image_field,
        description: str = 'Cover',
        pic_type: int = 3
    ) -> APIC | None:
        frame = None
        if image_field and hasattr(image_field, 'open'):
            image_field.open('rb')
            mime, _ = mimetypes.guess_type(image_field.name)
            if mime:
                frame = APIC(
                    encoding=3,
                    mime=mime,
                    type=pic_type,
                    desc=description,
                    data=image_field.read()
                )
            image_field.close()
        return frame

    def _apic_frame_to_temp_file(
        self,
        frame: APIC,
        description: str = "image"
    ) -> TemporaryUploadedFile | None:
        desc = frame.desc or description
        if ext := mimetypes.guess_extension(frame.mime):
            name = f"{desc}{ext}"
            tf = TemporaryUploadedFile(
                name, frame.mime, len(frame.data), "uft-8")
            tf.file.write(frame.data)
            tf.file.seek(0)
            if image_is_valid(tf):
                return tf
            os.remove(tf.temporary_file_path())
            return None

    def read(self, file: ID3FileType) -> dict[str, any]:
        self.tags = file.tags
        self.meta = {
            'duration': int(file.info.length)
        }
        album = {}
        artist_names = self.tags.get("TPE1")
        artist_names = artist_names.text if artist_names else []
        artists_map = {a: {'name': a} for a in artist_names}

        self._read_tag('TIT2', 'name')
        self._read_tag('TCON', 'genre')
        self._read_tag('TALB', 'name', album)
        self._read_tag('TDRC', 'year', value_processing_func=_process_id3_year)
        self._read_tag('TRCK', 'number',
                       value_processing_func=_process_id3_track)

        # Set album artist to TPE2 frame value or first available artist
        # This allows to create Album instance even when TPE2 frame is missing
        if album:
            self._read_tag("TPE2", "artist", album)
            if "artist" not in album and artist_names:
                self._set_if_present("artist", artist_names[0], album)

        # Extract all APIC frames for matching artist images
        apic_frames = [frame for frame in self.tags.values()
                       if isinstance(frame, APIC)]

        # Validate embedded images and attach them to album, artists or song
        for apic in apic_frames:
            if apic.type in [PictureType.MEDIA, PictureType.COVER_FRONT]:
                if album.get('artist'):
                    album['image'] = self._apic_frame_to_temp_file(apic)
                else:
                    self.meta['image'] = self._apic_frame_to_temp_file(apic)
            if apic.type == PictureType.ARTIST:
                if d := artists_map.get(apic.desc):
                    d["image"] = self._apic_frame_to_temp_file(apic)

        artists = list(artists_map.values())
        if "artist" in album:
            self.meta['album'] = album
        if artists:
            self.meta['artists'] = artists

        return self.meta

    def write(
        self,
        file: FieldFile = None,
        metadata: dict[str, any] = None,
        song: Song = None
    ) -> None:
        self.tags = ID3()

        if song:
            self.song_to_metadata(song)
            metadata = self.meta
            file = song.file
        elif file is None and metadata is None:
            msg = "`file` and `metadata` parameters must be provided"
            raise ValueError(msg)

        # Set basic fields
        if metadata.get('name'):
            self.tags.add(TIT2(encoding=3, text=metadata['name']))

        if metadata.get('year'):
            self.tags.add(TDRC(encoding=3, text=str(metadata['year'])))

        if metadata.get('genre'):
            self.tags.add(TCON(encoding=3, text=metadata['genre']))

        if metadata.get('number'):
            self.tags.add(TRCK(encoding=3, text=str(metadata['number'])))

        # Set artists and ther images(TPE1)
        if 'artists' in metadata and metadata['artists']:
            self._set_artist_tags(metadata['artists'])

        if album := metadata.get('album'):
            self._set_album_tags(album)

        # Add front cover image
        if metadata.get('image') and not album:
            if f := self._make_apic_frame(
                metadata['image'], metadata['name'], PictureType.COVER_FRONT
            ):
                self.tags.add(f)

        if isinstance(file, FieldFile):
            self.tags.save(file.path)
        else:
            self.tags.save(file.temporary_file_path())

    def _set_artist_tags(
        self,
        artists: list,
    ):
        artist_names = [artist['name'] for artist in artists]
        self.tags.add(TPE1(encoding=3, text=artist_names))
        for artist in artists:
            if 'image' in artist:
                if f := self._make_apic_frame(
                    artist['image'],
                    artist['name'],
                    PictureType.ARTIST
                ):
                    self.tags.add(f)

    def _set_album_tags(self, album: dict):
        if album:
            if album.get('name'):
                self.tags.add(TALB(encoding=3, text=album['name']))
            if album.get('artist'):
                self.tags.add(TPE2(encoding=3, text=album['artist']))
            if album.get('image'):
                if f := self._make_apic_frame(
                    album['image'], album['name'], PictureType.COVER_FRONT
                ):
                    self.tags.add(f)


# class MP4Editor(Editor):
#     async def read_metadata(self, file: MP4) -> Dict[str, Any]:
#         tags = file.tags
#
#         def get_tag(key, default=None):
#             return tags.get(key, [default])[0]
#
#         metadata = {
#             "name": get_tag("\xa9nam"),
#             "year": int(get_tag("\xa9day", "")[:4]) if get_tag("\xa9day") else None,
#             "genre": get_tag("\xa9gen"),
#             "number": get_tag("trkn", [(1,)])[0],
#             "artists": [{"name": name} for name in tags.get("\xa9ART", [])],
#             "duration": int(file.info.length)
#         }
#
#         if album_name := get_tag("\xa9alb"):
#             metadata["album"] = {
#                 "name": album_name,
#                 "year": int(get_tag("\xa9day", "")[:4]) if get_tag("\xa9day") else None,
#                 "genre": get_tag("\xa9gen"),
#                 "image": tags.get("covr", [None])[0]
#             }
#             artist = get_tag("aART")
#             if artist:
#                 metadata["album"]["artist"] = {
#                     "name": artist
#                 }
#         else:
#             metadata["image"] = tags.get("covr", [None])[0]
#
#         return metadata
#
#     async def write_metadata(
#         self,
#         file: FieldFile = None,
#         metadata: Dict[str, Any] = None,
#         song: Song = None
#     ) -> None:
#         if song:
#             metadata = self.song_to_metadata(song)
#             file = song.file
#         elif file is None or metadata is None:
#             raise ValueError("`file` and `metadata` must be provided")
#
#         mp4 = MP4(file.path)
#
#         if name := metadata.get("name"):
#             mp4["\xa9nam"] = [name]
#         if year := metadata.get("year"):
#             mp4["\xa9day"] = [str(year)]
#         if genre := metadata.get("genre"):
#             mp4["\xa9gen"] = [genre]
#         if number := metadata.get("number"):
#             mp4["trkn"] = [(number, 0)]
#
#         if artists := metadata.get("artists"):
#             mp4["\xa9ART"] = [a["name"] for a in artists]
#
#         if album := metadata.get("album"):
#             if album_name := album.get("name"):
#                 mp4["\xa9alb"] = [album_name]
#             if album_artist := album.get("artist"):
#                 mp4["aART"] = [album_artist]
#             if album_image := album.get("image"):
#                 await sync_to_async(self._store_image)(album_image, mp4)
#         elif image := metadata.get("image"):
#             await sync_to_async(self._store_image)(image, mp4)
#
#         await sync_to_async(mp4.save)()
#
#     def _store_image(self, image_field: FieldFile, tags: MP4):
#         ext = os.path.splitext(image_field.path)
#         if ext == ".png":
#             format = MP4Cover.FORMAT_PNG
#         elif ext == ".jpg":
#             format = MP4Cover.FORMAT_JPEG
#         else:
#             return
#
#         image_field.open("rb")
#         tags["covr"] = [MP4Cover(image_field.read(), imageformat=format)]
#         image_field.close()
#
#

_editors = [ID3Editor()]
_extension_map = {
    '.mp3': _editors[0],
}


def read_metadata(file: TemporaryUploadedFile) -> dict:
    if filetype := File(file):
        if isinstance(filetype, ID3FileType):
            return ID3Editor().read(filetype)
    return None


def write_metadata(song: Song) -> dict:
    file = song.file
    editor = _extension_map.get(os.path.splittext(file.path)[1])
    if editor:
        editor.write(song=song)
