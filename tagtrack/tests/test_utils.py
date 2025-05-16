from .helper import TestHelper
from tagtrack import utils


class TestUtils(TestHelper):
    def test_image_validation(self):
        f1 = self.temp_file('image.jpg')
        f2 = self.temp_file('junk.jpg')

        self.assertFalse(utils.validate_image(f1))
        self.assertTrue(utils.validate_image(f2))
