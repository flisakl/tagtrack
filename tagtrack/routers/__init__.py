from ninja import Router

from .artists import router as artists_router


router = Router()
router.add_router("/artists", artists_router)


__all__ = ['router']
