from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db.models.fields.files import FieldFile
from typing import Dict, Any
from mutagen import File
from mutagen.id3 import ID3FileType, PictureType, ID3
from mutagen.id3 import APIC, TPE1, TPE2, TALB, TIT2, TDRC, TCON, TRCK
from mutagen._constants import GENRES
from .models import Song
import mimetypes


class Editor:
    def read_metadata(self, file) -> Dict[str, Any]:
        raise NotImplementedError()

    def write_metadata(
        self,
        file: FieldFile,
        metadata: Dict[str, Any]
    ) -> None:
        raise NotImplementedError()

    def _set_genre(self, genre: str, data: dict):
        if genre and genre in GENRES:
            data['genre'] = genre

    # Attach image helper
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

    def song_to_metadata(self, song: Song) -> dict:
        meta = {
            'name': song.name,
            'number': song.number,
            'year': song.year
        }
        self._set_genre(song.genre, meta)
        if song.image:
            meta['image'] = song.image

        if song.album:
            album = song.album
            alb = {
                'name': album.name,
                'artist': album.artist.name,
            }
            self._set_genre(album.genre, alb)
            if album.year:
                alb['year'] = album.year
            if album.image:
                alb['image'] = album.image
            meta['album'] = alb
        artists = []
        for art in song.artists.all():
            data = {
                'name': art.name,
            }
            if art.image:
                data['image'] = art.image
            artists.append(data)
        meta['artists'] = artists

        return meta


class ID3Editor(Editor):
    def read_metadata(self, file: ID3FileType) -> Dict[str, Any]:
        tags = file.tags

        genre = tags.get('TCON').text[0] if tags.get('TCON') else None
        album_name = tags.get('TALB').text[0] if tags.get('TALB') else None

        # Extract year as a four-digit number if available
        album_year_raw = tags.get('TDRC').text[0] if tags.get('TDRC') else None
        album_year = int(str(album_year_raw)[:4]) if album_year_raw else None

        album_artist = tags.get('TPE2').text[0] if tags.get('TPE2') else None
        artists_raw = tags.get('TPE1').text if tags.get('TPE1') else []
        track_number = int(tags.get('TRCK').text[0].split(
            '/')[0]) if tags.get('TRCK') else 1
        track_image = None

        # Extract all APIC frames for matching artist images
        apic_frames = [
            frame for frame in tags.values()
            if isinstance(frame, APIC)]

        def find_image_for_name(name: str):
            for apic in apic_frames:
                if apic.desc.strip().lower() == name.strip().lower():
                    return apic
            return None

        # Album image (PictureType is COVER_FRONT or MEDIA)
        album_image = None
        for apic in apic_frames:
            if apic.type in [PictureType.MEDIA, PictureType.COVER_FRONT]:
                if album_name:
                    album_image = apic
                else:
                    track_image = apic
                break

        artists: list[Dict[str, Any]] = []
        for name in artists_raw:
            artists.append({
                "name": name,
                "image": find_image_for_name(name)
            })

        album_artist_name = album_artist or (
            artists[0]['name'] if artists else None
        )
        if album_artist_name:
            album_artist = {
                'name': album_artist_name,
                'image': find_image_for_name(album_artist_name)
            }
        else:
            album_artist = None

        album = None
        if album_name:
            album = {
                "name": album_name,
                "image": album_image,
                "year": album_year,
                "artist": album_artist,
                "genre": genre,
            }

        metadata = {
            "album": album,
            "name": tags.get('TIT2').text[0] if tags.get('TIT2') else 'unnamed',
            "year": album_year,
            "genre": genre,
            "duration": int(file.info.length),
            "number": track_number,
            "artists": artists,
            "image": track_image
        }

        return metadata

    def write_metadata(
        self,
        file: FieldFile,
        metadata: Dict[str, Any]
    ) -> None:
        tags = ID3()

        # Set basic fields
        if metadata.get('name'):
            tags.add(TIT2(encoding=3, text=metadata['name']))

        if metadata.get('year'):
            tags.add(TDRC(encoding=3, text=str(metadata['year'])))

        if metadata.get('genre'):
            tags.add(TCON(encoding=3, text=metadata['genre']))

        if metadata.get('number'):
            tags.add(TRCK(encoding=3, text=str(metadata['number'])))

        # Set artists and ther images(TPE1)
        if 'artists' in metadata and metadata['artists']:
            self._set_artist_tags(metadata['artists'], tags)

        if album := metadata.get('album'):
            self._set_album_tags(album, tags)

        # Add front cover image
        if metadata.get('image') and not album:
            if f := self._make_apic_frame(
                metadata['image'], 'TrackCover', PictureType.COVER_FRONT
            ):
                tags.add(f)

        tags.save(file.path)

    def _set_artist_tags(
        self,
        artists: list,
        tags: ID3
    ):
        artist_names = [artist['name'] for artist in artists]
        tags.add(TPE1(encoding=3, text=artist_names))
        for artist in artists:
            if artist['image']:
                if f := self._make_apic_frame(
                    artist['image'],
                    artist['name'],
                    PictureType.ARTIST
                ):
                    tags.add(f)

    def _set_album_tags(self, album: dict, tags: ID3):
        if album:
            if album.get('name'):
                tags.add(TALB(encoding=3, text=album['name']))
            if album.get('artist'):
                tags.add(TPE2(encoding=3, text=album['artist']))
            if album.get('image'):
                if f := self._make_apic_frame(
                    album['image'], album['name'], PictureType.COVER_FRONT
                ):
                    tags.add(f)


def read_metadata(file: TemporaryUploadedFile) -> dict:
    f = File(file.temporary_file_path())
    if f:
        if issubclass(f.__class__, ID3FileType):
            editor = ID3Editor()

        return editor.read_metadata(f)
    return None
