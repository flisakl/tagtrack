from .helper import TestHelper
from tagtrack import utils
from ninja.errors import ValidationError


class TestUtils(TestHelper):
    def test_image_validation(self):
        f1 = self.temp_file('image.jpg', upload_filename='valid_image.jpg')
        f2 = self.temp_file('junk.jpg', upload_filename='invalid_image.jpg')
        f3 = None

        self.assertTrue(utils.image_is_valid(f1))
        self.assertFalse(utils.image_is_valid(f2))
        self.assertFalse(utils.image_is_valid(f3))

    def test_audio_file_validation(self):
        f1 = self.temp_file('song.mp3', 'audio/mpeg')
        f2 = self.temp_file('junk.mp3', 'audio/mpeg')
        f3 = None

        self.assertTrue(utils.audio_is_valid(f1))
        self.assertFalse(utils.audio_is_valid(f2))
        self.assertFalse(utils.audio_is_valid(f3))

    def test_raising_validation_error_for_images(self):
        f1 = self.temp_file('image.jpg', 'image/jpeg')
        f2 = self.temp_file('junk.jpg', 'image/jpeg')
        f3 = None

        self.assertRaises(ValidationError, utils.raise_on_invalid_image, f3, raise_on_none=True)
        self.assertRaises(ValidationError, utils.raise_on_invalid_image, f2, raise_on_none=True)
        self.assertRaises(ValidationError, utils.raise_on_invalid_image, f2, raise_on_none=False)
        utils.raise_on_invalid_image(f3, raise_on_none=False)
        utils.raise_on_invalid_image(f1, raise_on_none=True)
        utils.raise_on_invalid_image(f1, raise_on_none=False)

    def test_raising_validation_error_for_audio_files(self):
        f1 = self.temp_file('song.mp3', 'audio/mpeg')
        f2 = self.temp_file('junk.mp3', 'audio/mpeg')
        f3 = None

        self.assertRaises(ValidationError, utils.raise_on_invalid_audio_file, f3, raise_on_none=True)
        self.assertRaises(ValidationError, utils.raise_on_invalid_audio_file, f2, raise_on_none=True)
        self.assertRaises(ValidationError, utils.raise_on_invalid_audio_file, f2, raise_on_none=False)
        utils.raise_on_invalid_audio_file(f3, raise_on_none=False)
        utils.raise_on_invalid_audio_file(f1, raise_on_none=True)
        utils.raise_on_invalid_audio_file(f1, raise_on_none=False)
