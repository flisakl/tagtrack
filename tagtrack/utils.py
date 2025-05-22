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
from os import path

from tagtrack.models import Album, Song


def make_error(loc: list[str], field_name: str, msg: str):
    l = loc.copy()
    l.append(field_name)
    return {
        "loc": l,
        "msg": _(msg)
    }


async def validate_audio_file(
    audio: TemporaryUploadedFile | None,
    loc: list[str] = ['form'],
    field: str = 'file'

) -> None | ValidationError:
    """Returns ValidationError when audio file is invalid"""
    if audio is None:
        return audio

    err = make_error(loc, field, _('File is not an audio file'))
    ve = ValidationError([err])
    if "audio" not in audio.content_type:
        return ve

    cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio.temporary_file_path()
        ]
    try:
        await sync_to_async(subprocess.run)(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True, text=True)
    except Exception:
        return ve
    return None


async def validate_image(
    image: TemporaryUploadedFile,
    loc: list[str] = ['form'],
    field: str = 'image'

) -> None | ValidationError:
    """Returns ValidationError when image is invalid"""
    if image is None:
        return image

    err = make_error(loc, field, _('File is not an image'))
    ve = ValidationError([err])
    if "image" not in image.content_type:
        return ve

    try:
        im = await sync_to_async(Image.open)(image.temporary_file_path())
        await sync_to_async(im.verify)()
    except Exception:
        return ve
    return None


async def get_or_set_from_cache(key: str, qs, obj_pk: int = None):
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
    song.image = album.image
    song.genre = song.genre if song.genre else album.genre
    song.year = song.year if song.year else album.year


def _make_temp_image(frame: APIC) -> TemporaryUploadedFile:
    tf = TemporaryUploadedFile(
        frame.desc, content_type=frame.mime, size=0, charset=frame.encoding
    )
    tf.file.write(frame.data)
    tf.file.seek(0)
    return tf


async def make_tempfile_from_apic_frame(frame: APIC | None):
    if not frame:
        return None
    elif frame.mime == '->':
        return None

    tf = await sync_to_async(_make_temp_image)(frame)
    if not await validate_image(tf):
        return tf
    return None


async def make_zip_file(songs: list[Song]):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as zf:
        for s in songs:
            zf.write(s.file.path, path.basename(s.file.path))
    buffer.seek(0)
    return buffer


class CloseFileResponse(FileResponse):
    def close(self):
        super().close()
        if hasattr(self._file, 'close'):
            self._file.close()
