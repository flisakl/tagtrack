from django.utils.translation import gettext_lazy as _
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.shortcuts import aget_object_or_404
from django.core.cache import cache
from asgiref.sync import sync_to_async
from PIL import Image


def make_error(loc: list[str], field_name: str, msg: str):
    loc.append(field_name)
    return {
        "loc": loc,
        "msg": _(msg)
    }


def validate_image(image: TemporaryUploadedFile) -> bool:
    """Checks if uploaded image is actual image file."""
    if "image" not in image.content_type:
        return False

    try:
        Image.open(image.temporary_file_path()).verify()
    except Exception:
        return False
    return True


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
