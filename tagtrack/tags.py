from django.core.files.uploadedfile import TemporaryUploadedFile
from abc import ABC, abstractmethod
from typing import Dict, Any
from mutagen import File
from mutagen.id3 import ID3FileType, PictureType
from mutagen.id3 import APIC, TPE1, TPE2, TALB, TIT2, TDRC, TCON, TRCK


class Editor(ABC):
    @abstractmethod
    def read_metadata(self, file) -> Dict[str, Any]:
        pass

    @abstractmethod
    def write_metadata(self, file, metadata: Dict[str, Any]) -> None:
        pass


class ID3Editor(Editor):
    def read_metadata(self, file: ID3FileType) -> Dict[str, Any]:
        tags = file.tags

        album_name = tags.get('TALB').text[0] if tags.get('TALB') else None

        # Extract year as a four-digit number if available
        album_year_raw = tags.get('TDRC').text[0] if tags.get('TDRC') else None
        album_year = int(str(album_year_raw)[:4]) if album_year_raw else None

        album_artist = tags.get('TPE2').text[0] if tags.get('TPE2') else None
        artists_raw = tags.get('TPE1').text if tags.get('TPE1') else []
        track_number = int(tags.get('TRCK').text[0].split('/')[0]) if tags.get('TRCK') else 1
        track_image = None

        # Extract all APIC frames for matching artist images
        apic_frames = [frame for frame in tags.values() if isinstance(frame, APIC)]

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
                "artist": album_artist
            }

        metadata = {
            "album": album,
            "name": tags.get('TIT2').text[0] if tags.get('TIT2') else 'unnamed',
            "year": album_year,
            "genre": tags.get('TCON').text[0] if tags.get('TCON') else None,
            "duration": int(file.info.length),
            "number": track_number,
            "artists": artists,
            "image": track_image
        }

        return metadata

    def write_metadata(self, file, metadata: Dict[str, Any]) -> None:
        raise NotImplementedError("write_metadata not implemented yet")


def read_metadata(file: TemporaryUploadedFile) -> dict:
    f = File(file.temporary_file_path())
    if f:
        if issubclass(f.__class__, ID3FileType):
            editor = ID3Editor()

        return editor.read_metadata(f)
    return None
