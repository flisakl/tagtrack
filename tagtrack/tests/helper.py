import shutil
from os import path
from django.test import TestCase
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.conf import settings


class TestHelper(TestCase):
    def load_file(self, path: str, mode: str = 'rb'):
        return open(path, mode)

    def temp_file(self, name: str = 'image.jpg', mime: str = 'image/jpeg',
                  upload_filename: str = None):
        fname = upload_filename if upload_filename else name
        tuf = TemporaryUploadedFile(fname, mime, 0, 'utf-8')
        fp = path.join(path.dirname(__file__), name)
        file = self.load_file(fp)
        tuf.file.write(file.read())
        file.close()
        return tuf

    def file_exists(self, dir: str, fname: str):
        fpath = path.join(settings.MEDIA_ROOT, dir, fname)
        return path.isfile(fpath)

    @classmethod
    def tearDownClass(cls):
        dirnames = ['artists', 'albums', 'songs', 'singles']
        paths = [f"{path.join(settings.MEDIA_ROOT, x)}" for x in dirnames]
        for p in paths:
            shutil.rmtree(p, ignore_errors=True)
