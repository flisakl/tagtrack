from ninja import Router

from .artists import router as artists_router
from .albums import router as albums_router


router = Router()
router.add_router("/artists", artists_router)
router.add_router("/albums", albums_router)


__all__ = ['router']
