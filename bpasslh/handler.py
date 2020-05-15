import re
import os.path
import requests
import collections
import shapely
import shapely.geometry
import fiona
from glob import glob
from .util import csv_to_named_tuple


DATA_DIR = "data"


GeneralisedData = collections.namedtuple(
    "GeneralisedData",
    [
        "species_name",
        "latitude",
        "longitude",
        "location_generalisation",
        "ala_species_name",
    ],
)


def one(l):
    assert type(l) == list
    assert len(l) == 1
    return l[0]


def normalise_species_name(sn):
    if sn is None:
        return
    return sn.lower().strip()


def resolve_package_path(rel_path):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), rel_path))


class ALASpeciesLookup:
    def __init__(self, logger):
        self._logger = logger
        self._cache = {}
        self.url = "https://bie.ala.org.au/ws/species/lookup/bulk"

    def get_bulk(self, species_names):
        """
        Find standard name for given the species from ALA.
        using the bulklookup name service.
        """
        species_names = list(map(normalise_species_name, species_names))
        # we don't bother using the cache for bulk requests, but
        # it's there to handle one-off queries later on
        response = self._ala_lookup(species_names)
        self._logger.debug("ALASpeciesLookup.get_bulk({})".format(species_names))
        ala_names = []
        for species_name, result in zip(species_names, response):
            ala_name = normalise_species_name(result.get("name"))
            self._cache[species_name] = ala_name
            ala_names.append(ala_name)
        return ala_names

    def get(self, species_name):
        species_name = normalise_species_name(species_name)
        if species_name in self._cache:
            return self._cache[species_name]
        return self.get_bulk([species_name])[0]

    def _ala_lookup(self, species_names):
        response = requests.post(self.url, json={"names": species_names})
        result = response.json()
        if response.status_code != 200 or not result:
            raise Exception(
                "ALASpeciesLookup: {} -> {}/{}".format(
                    species_names, response.status_code, result
                )
            )
        return result


class GeneralisationRules:
    WITHHOLD = "WITHHOLD"
    KM = re.compile(r"^(\d+)km$")


class Generalisation:
    def __init__(self, generalisation_expression):
        self.expression = generalisation_expression
        self._parse(self.expression)

    def apply(self, latitude, longitude):
        if self.expression is None:
            return longitude, latitude

        if self.withhold:
            latitude = longitude = None
        elif self.km is not None:
            if latitude and longitude:
                latitude, longitude = self._generalise(latitude, longitude, self.km)
            else:
                latitude = longitude = None
        return latitude, longitude

    def _generalise(self, latitude, longitude, km):
        if km < 10:
            rounded_lat = round(latitude, 2)
            rounded_long = round(longitude, 2)
        elif km >= 10 and km < 100:
            rounded_lat = round(latitude, 1)
            rounded_long = round(longitude, 1)
        elif km > 100:
            rounded_lat = round(latitude, 0)
            rounded_long = round(longitude, 0)

        return rounded_lat, rounded_long

    def _parse(self, expression):
        # defaults
        self.withhold = False
        self.km = None
        if expression is None:
            return
        if expression == GeneralisationRules.WITHHOLD:
            self.withhold = True
            return
        m = GeneralisationRules.KM.match(expression)
        if m:
            self.km = int(m.groups()[0])
        else:
            self._logger.error(
                "Unrecognised generalisation expression: %s" % expression
            )


class AustralianStates:
    def __init__(self):
        self._shapes = None

    def _get_shapes(self):
        # note: lazy initialisation of the shape lookup
        if self._shapes is None:
            self._shapes = list(self._load_shapes())
        assert len(self._shapes) > 0
        return self._shapes

    def lookup(self, lat, lng):
        self._get_shapes()
        point = shapely.geometry.Point(lng, lat)
        for location, bounds, state_shape in self._shapes:
            # optimisation: if the point isn't in the bbox of the state,
            # don't do the much slower check against the full boundaries
            if not bounds.contains(point):
                continue
            if state_shape.contains(point):
                return location

    def _load_shapes(self):
        psma_dir = self._get_psma_directory()
        for state_dir in glob(psma_dir + "/*/"):
            state = state_dir.split("/")[-2]
            shapefile_path = one(glob(state_dir + "*.shp"))
            with fiona.open(shapefile_path) as coll:
                for state_shape_record in coll:
                    shape = shapely.geometry.asShape(state_shape_record["geometry"])
                    minx, miny, maxx, maxy = shape.bounds
                    bounds_poly = shapely.geometry.Polygon(
                        [(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)]
                    )
                    yield state, bounds_poly, shape

    def _get_psma_directory(self):
        return resolve_package_path("./{}/shapefiles/PSMA/".format(DATA_DIR))


class SensitiveDataGeneraliser:
    DEFAULT_GENERALISATION = "1km"

    def __init__(self, logger):
        self._logger = logger
        self.sensitive_files_path = self._get_sensitive_files_path()
        self._load_sensitive_species_data()
        self.ala_lookup = ALASpeciesLookup(self._logger)
        self.states = AustralianStates()

    def _get_sensitive_files_path(self):
        return resolve_package_path("./" + DATA_DIR)

    def _load_sensitive_species_data(self):
        self.sensitive_species_map = {}
        for csv in glob(os.path.join(self.sensitive_files_path, "*.csv")):
            location = os.path.splitext(os.path.basename(csv))[0]
            _, rows = csv_to_named_tuple("SensitiveData", csv)
            data = {}
            for row in rows:
                sn = normalise_species_name(row.scientificname)
                data[sn] = getattr(row, "generalisation", self.DEFAULT_GENERALISATION)
            self.sensitive_species_map[location] = data
        self._all_sensitive_species_names = set()
        for species_map in self.sensitive_species_map.values():
            self._all_sensitive_species_names |= set(species_map.keys())

    def _get_generalisation_expression(self, state, species_name):
        return self.sensitive_species_map[state].get(
            normalise_species_name(species_name)
        )

    def check_species_sensitivity(self, state, species_name):
        # optimisation: if this species isn't sensitive in any state
        # we can skip doing # expensive location determination
        if species_name not in self._all_sensitive_species_names:
            return

        return self._get_generalisation_expression(state, species_name)

    def generalise_australia(self, species_name, state, latitude, longitude):
        ala_species_name = self.ala_lookup.get(species_name)
        return self.check_species_sensitivity(
            state, ala_species_name
        ) or self.check_species_sensitivity(state, species_name)

    def apply(self, species_name, latitude, longitude):
        if latitude is None or longitude is None:
            return

        state = self.states.lookup(latitude, longitude)
        ala_species_name = None

        expr = self.DEFAULT_GENERALISATION
        # we only query the ALA species database if in Australia
        if state is not None:
            expr = self.generalise_australia(species_name, state, latitude, longitude)

        lat, lon = Generalisation(expr).apply(latitude, longitude)

        return GeneralisedData(species_name, lat, lon, expr, ala_species_name)
