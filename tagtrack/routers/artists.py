from ninja import Router, Form, File, UploadedFile
from django.conf import settings
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from ninja.errors import ValidationError

from tagtrack import utils
from tagtrack.models import Artist
from .schemas import (
    ArtistSchemaIn, ArtistSchemaOut,
)

router = Router(tags=["Artists"])


@router.post(
    '',
    response={201: ArtistSchemaOut},
    auth=settings.TAGTRACK_AUTH['CREATE']
)
async def create_artist(
    request,
    form: Form[ArtistSchemaIn],
    image: UploadedFile | None = File(None)
):
    errors = []
    try:
        artist = Artist(**form.dict(exclude_unset=True))
        # Validate the image if provided
        if image:
            if utils.validate_image(image):
                artist.image = image
            else:
                err = utils.make_error(
                    ['form'], 'image', _('File is not an image')
                )
                errors.append(err)

    except IntegrityError:
        errors.append(
            utils.make_errors(['form'], 'name', _('Artist already exists'))
        )

    if errors:
        raise ValidationError(errors)
    else:
        await artist.asave()
        return 201, artist
