import app

# TODO(Implement flask-sqlalchemy.)


class TestApp(object):
    def setup(self):
        app.app.config['TESTING'] = True
        self.app = app.app.test_client()

    def teardown(self):
        pass

    def test_index(self):
        rv = self.app.get('/')
        assert rv is not None

    # TODO(Test whether the profile returns the stats get.)
    # TODO(Test for all regions and known usernames/ids.)
    # TODO(Abstract out the retrieval of the ID. Or mock it.)
    def test_profile(self):
        pass

        # rv = self.app.get('/api/champions/tartio/na/')
        # assert rv == app.stats('tartio', "27284", "na")
