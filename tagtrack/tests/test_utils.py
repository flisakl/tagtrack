from .helper import TestHelper
from tagtrack import utils


class TestUtils(TestHelper):
    async def test_image_validation(self):
        f1 = self.temp_file('image.jpg')
        f2 = self.temp_file('junk.jpg')

        self.assertFalse(await utils.validate_image(f1))
        self.assertTrue(await utils.validate_image(f2))

    async def test_audio_file_validation(self):
        f1 = self.temp_file('song.mp3', 'audio/mpeg')
        f2 = self.temp_file('junk.mp3', 'audio/mpeg')

        self.assertFalse(await utils.validate_audio_file(f1))
        self.assertTrue(await utils.validate_audio_file(f2))
