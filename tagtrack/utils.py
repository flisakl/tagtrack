from django.utils.translation import gettext_lazy as _
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.shortcuts import aget_object_or_404
from django.core.cache import cache
from ninja.errors import ValidationError
from asgiref.sync import sync_to_async
from PIL import Image
from mutagen import File

from tagtrack.models import Album, Song


def make_error(loc: list[str], field_name: str, msg: str):
    l = loc.copy()
    l.append(field_name)
    return {
        "loc": l,
        "msg": _(msg)
    }


def validate_audio_file(
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

    try:
        if not File(audio.file):
            return ve
    except Exception:
        return ve
    return None


def validate_image(
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
        Image.open(image.temporary_file_path()).verify()
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
