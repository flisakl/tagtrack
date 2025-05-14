from django.utils.translation import gettext_lazy as _
from django.core.files.uploadedfile import TemporaryUploadedFile
from PIL import Image


def make_errors(loc: list[str], field_name: str, msg: str):
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
