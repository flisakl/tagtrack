# Tagtrack

REST API for editing audio files metadata.

Supported formats:
- [X] mp3
- [X] mp4
- [x] ogg
- [x] opus
- [x] flac

## How to use

**ffmpeg** is required for validating audio files.

1. Add application to INSTALLED_APPS
```python
INSTALLED_APPS = [
    'tagtrack'
]
```
2. Run migrations
```bash
python manage.py migrate
```
3. Configure settings
```python
TAGTRACK_AUTH = {
    # Value will be passed as `auth` parameter to corresponding endpoints
    "DEFAULT": {
        "CREATE": None,        
        "READ": None,        
        "UPDATE": None,        
        "DELETE": None,        
        "DOWNLOAD": None,        
    }
    # You can also set authentication settings for each router separately
    "SONG": {},
    "ALBUM": {},
    "ARTIST": {},
}

# Maximum number of songs to download per one request
# Applies only to songs router endpoint for downloading songs picked by user.
TAGTRACK_MAX_SONG_DOWNLOAD = 20

FILE_UPLOAD_HANDLERS = [
    "django.core.files.uploadhandler.TemporaryFileUploadHandler"
]
```
