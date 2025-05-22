from django.conf import settings

__version__ = "0.0.1"

default = {
    'CREATE': None,
    'READ': None,
    'UPDATE': None,
    'DELETE': None,
    'DOWNLOAD': None,
}

MAX_SONG_DOWNLOAD = getattr(
    settings,
    "TAGTRACK_MAX_SONG_DOWNLOAD",
    20
)


def _set_auth_from_settings(key_to_check: str):
    tagtrack_auth = getattr(settings, "TAGTRACK_AUTH", None)
    if tagtrack_auth and isinstance(tagtrack_auth, dict):
        value = tagtrack_auth.get(key_to_check)
        if isinstance(value, dict):
            return value
    return None


auth_settings = getattr(settings, "TAGTRACK_AUTH", None)
if auth_settings:
    AUTH = _set_auth_from_settings("DEFAULT") or default
    SONG_AUTH = _set_auth_from_settings("SONG") or AUTH
    ALBUM_AUTH = _set_auth_from_settings("ALBUM") or AUTH
    ARTIST_AUTH = _set_auth_from_settings("ARTIST") or AUTH
else:
    AUTH = SONG_AUTH = ALBUM_AUTH = ARTIST_AUTH = default
