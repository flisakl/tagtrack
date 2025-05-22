from .helper import TestHelper


class TestModels(TestHelper):
    async def test_song_needs_to_be_retagged_after_artist_is_modified(self):
        art = await self.create_artist()
        s = await self.create_song(self.temp_file(), artists=[art])
        self.assertFalse(s.retag)

        art.name = 'Test Name'
        await art.asave()

        await s.arefresh_from_db()
        self.assertTrue(s.retag)

    async def test_song_needs_to_be_retagged_after_album_is_modified(self):
        art = await self.create_artist()
        alb = await self.create_album(art)
        s = await self.create_song(self.temp_file(), album=alb)
        self.assertFalse(s.retag)

        alb.name = 'Test Name'
        await alb.asave()

        await s.arefresh_from_db()
        self.assertTrue(s.retag)
