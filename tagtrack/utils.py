from django.utils.translation import gettext_lazy as _
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.shortcuts import aget_object_or_404
from django.core.cache import cache
from ninja.errors import ValidationError
from asgiref.sync import sync_to_async
from django.http import FileResponse
from PIL import Image
import subprocess
from mutagen.id3 import APIC
import io
import zipfile
import mimetypes
from os import path

from tagtrack.models import Album, Song


def make_error(loc: list[str], field_name: str, msg: str):
    local = loc.copy()
    local.append(field_name)
    return {
        "loc": local,
        "msg": _(msg)
    }


def audio_is_valid(audio: TemporaryUploadedFile):
    if audio is None or "audio" not in audio.content_type:
        return False

    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio.temporary_file_path()
    ]
    try:
        subprocess.run(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True, text=True)
    except Exception:
        return False
    return True


def raise_on_invalid_audio_file(
    audio: TemporaryUploadedFile | None,
    loc: list[str] = ['form'],
    field: str = 'file',
    raise_on_none: bool = False
) -> None | ValidationError:
    err = ValidationError([
        make_error(loc, field, _('File is not an audio file'))
    ])
    valid = audio_is_valid(audio)
    if ((raise_on_none and audio is None) or
       (audio is not None and not valid)):
        raise err


def image_is_valid(image: TemporaryUploadedFile):
    if image is None or "image" not in image.content_type:
        return False

    try:
        im = Image.open(image.temporary_file_path())
        im.verify()
    except Exception:
        return False
    return True


def raise_on_invalid_image(
    image: TemporaryUploadedFile,
    loc: list[str] = ['form'],
    field: str = 'image',
    raise_on_none: bool = False
) -> None | ValidationError:
    """Raise ValidationError when image is invalid"""
    err = ValidationError([
        make_error(loc, field, _('File is not an image'))
    ])
    valid = image_is_valid(image)
    if ((raise_on_none and image is None) or
       (image is not None and not valid)):
        raise err


async def get_or_set_from_cache(key: str, qs, obj_pk: int = None):
    key = f"tagtrack-{key}"
    data = await sync_to_async(cache.get)(key, None)
    if data is not None:
        return data
    if obj_pk:
        data = await aget_object_or_404(qs, pk=obj_pk)
    else:
        data = await sync_to_async(list)(qs)
    await sync_to_async(cache.set)(key,  data)
    return data


def fill_song_fields(song: Song, album: Album):
    if album:
        song.image = song.image if song.image else album.image
        song.genre = song.genre if song.genre else album.genre
        song.year = song.year if song.year else album.year


def _make_temp_image(frame: APIC) -> TemporaryUploadedFile:
    name = frame.desc or "temp"
    ext = mimetypes.guess_extension(frame.mime)
    if ext:
        name = f"{name}{ext}"
        tf = TemporaryUploadedFile(
            name, content_type=frame.mime, size=0, charset=frame.encoding
        )
        tf.file.write(frame.data)
        tf.file.seek(0)
        return tf
    return None


def make_tempfile_from_apic_frame(frame: APIC | None):
    if not frame:
        return None
    elif frame.mime == '->':
        return None

    tf = _make_temp_image(frame)
    if not raise_on_invalid_image(tf):
        return tf
    return None


async def make_zip_file(songs: list[Song]):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for s in songs:
            z.write(s.file.path, path.basename(s.file.path))
    buf.seek(0)
    return buf


class CloseFileResponse(FileResponse):
    def close(self):
        super().close()
        if hasattr(self._file, 'close'):
            self._file.close()
