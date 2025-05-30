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
    l = loc.copy()
    l.append(field_name)
    return {
        "loc": l,
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
    field: str = 'file'

) -> None | ValidationError:
    if audio_is_valid(audio):
        return
    err = make_error(loc, field, _('File is not an audio file'))
    raise ValidationError([err])


def image_is_valid(image: TemporaryUploadedFile):
    if "image" not in image.content_type or image is None:
        return False

    try:
        im = Image.open(image.temporary_file_path())
        im.verify()
    except Exception as e:
        return False
    return True


def raise_on_invalid_image(
    image: TemporaryUploadedFile,
    loc: list[str] = ['form'],
    field: str = 'image'

) -> None | ValidationError:
    """Returns ValidationError when image is invalid"""
    if image_is_valid(image):
        return
    err = make_error(loc, field, _('File is not an image'))
    raise ValidationError([err])


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
    song.image = album.image
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
