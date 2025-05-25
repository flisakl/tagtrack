from .artists import router as artists_router
from .albums import router as albums_router
from .songs import router as songs_router
from .router import router

router.add_router("/artists", artists_router)
router.add_router("/albums", albums_router)
router.add_router("/songs", songs_router)

__all__ = ['router']
