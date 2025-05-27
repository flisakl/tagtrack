from .helper import TestHelper
from tagtrack import utils


class TestUtils(TestHelper):
    def test_image_validation(self):
        f1 = self.temp_file('image.jpg', upload_filename='valid_image.jpg')
        f2 = self.temp_file('junk.jpg', upload_filename='invalid_image.jpg')

        self.assertTrue(utils.image_is_valid(f1))
        self.assertFalse(utils.image_is_valid(f2))

    def test_audio_file_validation(self):
        f1 = self.temp_file('song.mp3', 'audio/mpeg')
        f2 = self.temp_file('junk.mp3', 'audio/mpeg')

        self.assertTrue(utils.audio_is_valid(f1))
        self.assertFalse(utils.audio_is_valid(f2))
