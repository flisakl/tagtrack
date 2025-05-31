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

    async def test_song_fields_are_filled_properly(self):
        a1 = await self.create_artist()
        a2 = await self.create_artist('Johnny Cash')
        alb1 = await self.create_album(a1, 'Piano Man', 'Soft Rock', 1973, self.temp_file())
        alb2 = await self.create_album(a2, 'Man in Black', 'Rock', 1971, self.temp_file())
        s1 = await self.create_song(self.temp_file(), genre='Test Genre', year=2009, image=self.temp_file())              # all fields set on song model, no album
        s2 = await self.create_song(self.temp_file(), genre='Test Genre', year=2009, image=self.temp_file(), album=alb1)  # all fields set on song model, with album
        s3 = await self.create_song(self.temp_file(), genre=None, year=None)                    # missing fields, no album
        s4 = await self.create_song(self.temp_file(), genre=None, year=None, album=alb2)        # missing fields, with album

        utils.fill_song_fields(s1, None)
        utils.fill_song_fields(s2, alb1)
        utils.fill_song_fields(s3, None)
        utils.fill_song_fields(s4, alb2)

        self.assertEqual(s1.year, 2009)
        self.assertEqual(s1.genre, 'Test Genre')
        self.assertTrue(s1.image)
        self.assertEqual(s2.year, 2009)
        self.assertEqual(s2.genre, 'Test Genre')
        self.assertTrue(s2.image)

        self.assertEqual(s3.year, None)
        self.assertEqual(s3.genre, None)
        self.assertFalse(s3.image)
        self.assertEqual(s4.year, 1971)
        self.assertEqual(s4.genre, 'Rock')
        self.assertTrue(s4.image)
