from bpasslh.handler import (
    normalise_species_name,
    Generalisation,
    SensitiveDataGeneraliser,
    ALASpeciesLookup)
from bpasslh.util import make_logger

logger = make_logger(__name__)

# CQUniversity Rockhampton
TEST_PRECISE = (-23.3241, 150.5193)
TEST_SPECIES = "Lagorchestes asomatus"

class TestGeneralisation:
    generaliser = SensitiveDataGeneraliser()
    ala_lookup = ALASpeciesLookup()

    def test_sensitive_data_files(self):
        assert self.generaliser._get_sensitive_files_path()

    def test_sensitive_data(self):
        assert normalise_species_name('Lagorchestes asomatus') \
            in self.generaliser._all_sensitive_species_names

    def test_state_lookup(self):
        state = self.generaliser.states.lookup(*TEST_PRECISE)
        assert(state == 'qld')

    def test_generalisation(self):
        gen_withhold = Generalisation("WITHHOLD")
        latitude, longitude = gen_withhold.apply(
            *TEST_PRECISE)
        assert latitude is None and longitude is None

        gen_km = Generalisation("10km")
        latitude, longitude = gen_km.apply(
            *TEST_PRECISE)
        assert latitude == -23.3 and longitude == 150.5

    def test_sensitive_data_generalisation(self):
        generalised_data = self.generaliser.apply(
            TEST_SPECIES, *TEST_PRECISE)
        gen_data_dict = generalised_data._asdict()
        assert gen_data_dict
        assert all(
            key in gen_data_dict.keys() for key in [
                'species_name', 'latitude', 'longitude',
                'location_generalisation', 'ala_species_name'])

    def test_ala_species_lookup(self):
        species_names = [
            "Pseudantechinus macdonnellensis",
            "Lagorchestes asomatus",
            "caustis deserti",
            "Macropus rufus",
            "Macropus giganteus",
            "Lagorchestes asomatus"]

        for species, result in zip(species_names, self.ala_lookup.get_bulk(species_names)):
            assert result is not None
