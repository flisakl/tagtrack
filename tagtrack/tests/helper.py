from os import path
from django.test import TestCase
from django.core.files.uploadedfile import TemporaryUploadedFile


class TestHelper(TestCase):
    def load_file(self, path: str, mode: str = 'rb'):
        return open(path, mode)

    def temp_file(self, name: str = 'image.jpg', mime: str = 'image/jpeg'):
        tuf = TemporaryUploadedFile(name, mime, 0, 'utf-8')
        fp = path.join(path.dirname(__file__), name)
        file = self.load_file(fp)
        tuf.file.write(file.read())
        file.close()
        return tuf
