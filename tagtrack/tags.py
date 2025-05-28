from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db.models.fields.files import FieldFile
from mutagen import File, FileType, Tags
from mutagen.id3 import ID3FileType, PictureType, ID3
from mutagen.id3 import APIC, TPE1, TPE2, TALB, TIT2, TDRC, TCON, TRCK
from mutagen._constants import GENRES
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen._vorbis import VCommentDict
import os
import base64

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
        file: FieldFile = None,
        metadata: dict[str, any] = None,
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


class MP4Editor(Editor):
    def read(self, file: MP4) -> dict[str, any]:
        tags = file.tags
        metadata = {
            "duration": int(file.info.length)
        }
        artists = [{"name": name} for name in tags.get("\xa9ART", [])]

        def read_tag(
            key_to_set,
            tag_to_get,
            dict_to_set: dict = metadata,
            default: any = None,
            process_func: Callable = None
        ):
            if value := tags.get(tag_to_get, [default])[0]:
                if process_func:
                    value = process_func(value)
                dict_to_set[key_to_set] = value

        read_tag("name", "\xa9nam")
        read_tag("genre", "\xa9gen")
        read_tag("year", "\xa9day", process_func=lambda x: int(x[:4]))
        read_tag("number", "trkn", process_func=lambda x: x[0])

        # Set album, but only if artist is available
        if album_name := tags.get("\xa9alb"):
            album = {'name': album_name[0]}
            read_tag("artist", "aART", album)
            if "artist" not in album and artists:
                album["artist"] = artists[0]['name']
            if "artist" in album:
                metadata['album'] = album

        # Set album or song image
        if image := tags.get("covr"):
            if album["artist"]:
                album["image"] = self._cover_to_temp_file(
                    image[0], album['name'])
            else:
                metadata["image"] = self._cover_to_temp_file(
                    image[0], metadata.get('name', 'unnamed')
                )

        # Attach artists
        if artists:
            metadata["artists"] = artists

        return metadata

    def _cover_to_temp_file(
            self,
            image: MP4Cover,
            name: str
    ) -> TemporaryUploadedFile:
        if image.FORMAT_PNG:
            ext = ".png"
            mime = "image/png"
        else:
            ext = ".jpg"
            mime = "image/jpeg"
        fname = f"{name}{ext}"
        tf = TemporaryUploadedFile(fname, mime, 0, "utf-8")
        tf.file.write(image)
        if image_is_valid(tf):
            return tf
        os.remove(tf.temporary_file_path())

    def write(
        self,
        file: FieldFile = None,
        metadata: dict[str, any] = None,
        song: Song = None
    ) -> None:
        if song:
            self.song_to_metadata(song)
            metadata = self.meta
            file = song.file
        elif file is None or metadata is None:
            raise ValueError("`file` and `metadata` must be provided")

        mp4 = MP4(file.path)

        def set_tag_if_present(
            key,
            meta_key,
            process_func: Callable = None,
            meta_dict: dict = metadata
        ):
            if value := meta_dict.get(meta_key):
                if process_func:
                    value = process_func(value)
                if isinstance(value, list):
                    mp4[key] = value
                else:
                    mp4[key] = [value]

        set_tag_if_present("\xa9nam", "name")
        set_tag_if_present("\xa9day", "year", str)
        set_tag_if_present("\xa9gen", "genre")
        set_tag_if_present("trkn", "number", lambda x: (x, 0))
        set_tag_if_present("\xa9ART", "artists", lambda x: [
                           a["name"] for a in x])

        if album := metadata.get("album"):
            set_tag_if_present("\xa9alb", "name", meta_dict=album)
            set_tag_if_present("aART", "artist", meta_dict=album)
            set_tag_if_present(
                "covr", "image",
                lambda x: self._file_to_cover(x),
                meta_dict=album
            )
        else:
            set_tag_if_present(
                "covr", "image",
                lambda x: self._file_to_cover(x),
            )

        mp4.save()

    def _file_to_cover(self, image_field: FieldFile):
        ext = os.path.splitext(image_field.path)[1]
        if ext == ".png":
            format = MP4Cover.FORMAT_PNG
        elif ext == ".jpg":
            format = MP4Cover.FORMAT_JPEG
        else:
            return

        ret = MP4Cover(image_field.read(), imageformat=format)
        image_field.close()
        return ret


class VCommentEditor(Editor):
    def _get_pictures(self) -> list[Picture]:
        if isinstance(self.filetype, FLAC):
            return self.filetype.pictures

        block = self.tags.get('metadata_block_picture', [])
        pics = []
        for encoded_pic in block:
            try:
                data = base64.b64decode(encoded_pic)
            except (TypeError, ValueError):
                continue
            try:
                picture = Picture(data)
                pics.append(picture)
            except Exception:
                continue
        return pics

    def _picture_to_temp_file(
        self,
        picture: Picture,
        name: str
    ):
        ext = mimetypes.guess_extension(picture.mime)
        if ext:
            fname = f"{name}{ext}"
            tuf = TemporaryUploadedFile(fname, picture.mime, 0, "utf-8")
            tuf.file.write(picture.data)
            tuf.file.seek(0)
            if image_is_valid(tuf):
                return tuf

    def read(self, file: OggVorbis | OggOpus | FLAC) -> dict[str, any]:
        audio = file
        if not isinstance(audio.tags, VCommentDict):
            raise ValueError("File does not contain Vorbis comments")

        self.tags = audio.tags
        self.filetype = file
        self.meta = {"duration": int(file.info.length)}

        def set_if_present(
            key_to_set: str,
            key_to_get: str,
            dict_to_set: dict = self.meta,
            process_func: Callable = None
        ):
            if value := self.tags.get(key_to_get, [])[0]:
                if process_func:
                    value = process_func(value)
                dict_to_set[key_to_set] = value

        set_if_present("name", "TITLE")
        set_if_present("genre", "GENRE")
        set_if_present("year", "DATE", process_func=int)
        set_if_present("number", "TRACKNUMBER", process_func=int)

        album = {}
        pictures = self._get_pictures()

        artists = self.tags.get('ARTIST', [])
        artist_map = {a: {'name': a} for a in artists}
        if album_name := self.tags.get('ALBUM'):
            album['name'] = album_name[0]
            set_if_present("artist", "ALBUMARTIST", album)
            if 'artist' not in album and artists:
                album['artist'] = artists[0]

        # Create temp files for album, image and artists
        for p in pictures:
            if p.type in [PictureType.COVER_FRONT, PictureType.MEDIA]:
                if album.get('artist') and not album.get('image'):
                    if pic := self._picture_to_temp_file(p, album['name']):
                        album['image'] = pic
                elif not self.meta.get('image'):
                    name = self.meta.get('name', 'unnamed')
                    if pic := self._picture_to_temp_file(p, name):
                        self.meta['image'] = pic

            elif p.type == PictureType.ARTIST:
                if a_dict := artist_map.get(p.desc):
                    if pic := self._picture_to_temp_file(p, a_dict['name']):
                        a_dict['image'] = pic
        if artists:
            self.meta['artists'] = list(artist_map.values())
        if album and album.get('artist'):
            self.meta['album'] = album

        return self.meta

    def write(
        self,
        file: FieldFile = None,
        metadata: dict[str, any] = None,
        song: Song = None
    ) -> None:
        if song:
            self.song_to_metadata(song)
            metadata = self.meta
            file = song.file
        elif file is None or metadata is None:
            raise ValueError("`file` and `metadata` must be provided")

        audio = File(file.path, easy=True)
        if not isinstance(audio.tags, VCommentDict):
            raise ValueError("File format does not support Vorbis comments")

        self.filetype = audio
        self.tags: VCommentDict = audio.tags
        self.tags.clear()

        def set_tag(key: str, value: any, process_func: Callable = None):
            if value:
                if process_func:
                    value = process_func(value)
                self.tags[key.upper()] = value

        artists = metadata.get('artists', [])
        set_tag('title', metadata.get('name'))
        set_tag('genre', metadata.get('genre'))
        set_tag('date', metadata.get('year'), str)
        set_tag('tracknumber', metadata.get('number'), str)
        set_tag('artist', [a['name'] for a in artists])

        if album := metadata.get('album'):
            set_tag('album', album.get('name'))
            set_tag('albumartist', album.get('artist'))
            if im := album.get('image'):
                self._embed_picture(
                    im, album.get('name'), PictureType.COVER_FRONT,
                    isinstance(self.filetype, FLAC)
                )

        # Attach pictures
        for art in metadata.get('artists', []):
            if im := art.get('image'):
                self._embed_picture(
                    im, art['name'], PictureType.ARTIST,
                    isinstance(file, FLAC))
        audio.save()

    def _embed_picture(
        self,
        image_field: FieldFile,
        name: str,
        type: PictureType,
        flac: bool = False
    ):
        mime, _ = mimetypes.guess_type(image_field.path)
        if mime:
            p = Picture()
            p.type = type
            p.desc = name
            p.mime = mime
            p.data = image_field.read()
            if flac:
                self.filetype.add_picture(p)
            else:
                metablock = self.tags.get('metadata_block_picture', [])
                pdata = p.write()
                encoded = base64.b64encode(pdata)
                metablock.append(encoded.decode('ascii'))
                self.tags['metadata_block_picture'] = metablock


_editors = [ID3Editor(), MP4Editor(), VCommentEditor()]
_extension_map = {
    '.mp3': _editors[0],
    '.mp4': _editors[1],
    '.ogg': _editors[2],
    '.opus': _editors[2],
    '.flac': _editors[2],
}


def read_metadata(file: TemporaryUploadedFile) -> dict:
    if filetype := File(file):
        if isinstance(filetype, ID3FileType):
            return ID3Editor().read(filetype)
        if isinstance(filetype, MP4):
            return MP4Editor().read(filetype)
        if isinstance(filetype.tags, VCommentDict):
            return VCommentEditor().read(filetype)
    return None


def write_metadata(song: Song) -> dict:
    file = song.file
    editor = _extension_map.get(os.path.splittext(file.path)[1])
    if editor:
        editor.write(song=song)
