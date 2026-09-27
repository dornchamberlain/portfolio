# Tests use made-up records and mock connections; no real database is changed.
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from shelter.config import Settings, ConfigurationError
from shelter.records import normalize_records, DataValidationError
from shelter.filters import filter_records
from shelter.presentation import coordinates, selected_record, breed_counts, map_content
from shelter.repository import JsonRepository, MongoRepository, RepositoryError
from shelter.service import DashboardService
from shelter.app import create_app


# Start with a valid sample record, then override the fields needed for each test.
def animal(key='1', **changes):
    row = dict(id=key, animal_id='REPEATED', name='Test animal', animal_type='Dog',
               breed='Labrador Retriever Mix', sex_upon_outcome='Intact Female',
               age_upon_outcome_in_weeks=52, location_lat=30.27, location_long=-97.74)
    row.update(changes)
    return row


# Configuration checks: defaults, invalid values, and safe error messages.
class ConfigurationTests(unittest.TestCase):
    def test_demo_default_and_packaged_path(self):
        settings = Settings.from_env({})
        self.assertEqual(settings.mode, 'demo')
        self.assertTrue(settings.data_file.is_file())

    def test_bad_mode(self):
        with self.assertRaises(ConfigurationError):
            Settings.from_env({'SHELTER_MODE': 'unexpected'})

    def test_missing_and_bad_mongo_uri(self):
        for uri in ['', 'https://example.invalid']:
            with self.subTest(uri=uri), self.assertRaises(ConfigurationError):
                Settings.from_env({'SHELTER_MODE':'mongo', 'MONGODB_URI':uri})

    def test_secret_not_in_repr_or_validation_message(self):
        settings = Settings.from_env({'SHELTER_MODE':'mongo', 'MONGODB_URI':'mongodb://user:secret@localhost'})
        self.assertNotIn('secret', repr(settings))

    def test_invalid_ports(self):
        for port in ['bad', '0', '65536', '1.2']:
            with self.subTest(port=port), self.assertRaises(ConfigurationError):
                Settings.from_env({'PORT':port})

    def test_invalid_database_names(self):
        for name in ['', 'a/b', 'a.b']:
            with self.subTest(name=name), self.assertRaises(ConfigurationError):
                Settings.from_env({'MONGODB_DATABASE':name})


# Record checks cover identity, missing values, and the format sent to the table.
class RecordTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(normalize_records([]), [])

    def test_mongo_identity_and_projection(self):
        from bson import ObjectId
        key = ObjectId()
        rows = normalize_records([dict(_id=key, breed=' Dog ', private_field='omit')])
        self.assertEqual(rows[0]['id'], str(key))
        self.assertEqual(rows[0]['breed'], 'Dog')
        self.assertNotIn('private_field', rows[0])
        json.dumps(rows, allow_nan=False)

    def test_duplicate_record_ids_rejected(self):
        with self.assertRaises(DataValidationError):
            normalize_records([animal(), animal()])

    def test_repeat_animal_ids_allowed(self):
        self.assertEqual(len(normalize_records([animal('1'),animal('2')])),2)

    def test_missing_identity_rejected(self):
        for row in [{}, {'id':''}, None, {'id':[]}]:
            with self.subTest(row=row), self.assertRaises(DataValidationError):
                normalize_records([row])

    def test_invalid_numbers_become_unknown(self):
        for value in [-1, 'bad', True, math.nan, math.inf, None]:
            with self.subTest(value=value):
                self.assertIsNone(normalize_records([animal(age_upon_outcome_in_weeks=value)])[0]['age_upon_outcome_in_weeks'])


# Small examples make the expected rescue matches easy to check by hand.
class FilterTests(unittest.TestCase):
    def test_original_profiles(self):
        rows = [animal('water'), animal('mountain',breed='Siberian Husky',sex_upon_outcome='Intact Male'),
                animal('disaster',breed='Bloodhound',sex_upon_outcome='Intact Male'),animal('cat',animal_type='Cat')]
        for profile,key in [('WATER','water'),('MOUNTAIN','mountain'),('DISASTER','disaster')]:
            self.assertEqual([r['id'] for r in filter_records(rows,profile)],[key])
        self.assertEqual(len(filter_records(rows,'RESET')),4)

    def test_age_boundaries(self):
        for age, expected in [(0,1),(156,1),(156.01,0),(-1,0),(None,0),('bad',0),(True,0)]:
            with self.subTest(age=age):
                self.assertEqual(len(filter_records([animal(age_upon_outcome_in_weeks=age)],'WATER')),expected)

    def test_invalid_profile_does_not_reset(self):
        for value in ['invalid',None,{},[]]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                filter_records([animal()],value)


# Map and chart checks, including selection changes and missing coordinates.
class PresentationTests(unittest.TestCase):
    def test_selection_survives_reordering(self):
        a,b=animal('1'),animal('2')
        for rows in [[a,b],[b,a]]:
            self.assertEqual(selected_record(rows,['1'])[0]['id'],'1')

    def test_stale_selection_is_not_another_animal(self):
        row,message=selected_record([animal('2')],['1'])
        self.assertIsNone(row)
        self.assertIn('no longer',message)

    def test_empty_and_initial_selection(self):
        self.assertIsNone(selected_record([],[])[0])
        self.assertEqual(selected_record([animal()],[])[0]['id'],'1')

    def test_coordinate_validation(self):
        for lat,lon in [(91,0),(0,181),(-91,0),(0,-181),(None,0),(True,0),(math.inf,0)]:
            with self.subTest(lat=lat,lon=lon):
                self.assertIsNone(coordinates(animal(location_lat=lat,location_long=lon)))
        self.assertEqual(coordinates(animal(location_lat=0,location_long=0)),[0,0])
        self.assertEqual(coordinates(animal(location_lat=-90,location_long=180)),[-90,180])

    def test_map_uses_named_fields(self):
        # Reversing the fields checks that the map no longer depends on column positions.
        row=dict(reversed(list(animal().items())))
        self.assertEqual(map_content([row],['1']).center,[30.27,-97.74])

    def test_chart_counts_and_unknown(self):
        self.assertEqual(breed_counts([{'breed':'A'},{'breed':'A'},{'breed':None}]),[('A',2),('Unknown',1)])
        self.assertEqual(breed_counts([]),[])


# Mock reads let these tests cover both empty results and database failures.
class RepositoryServiceTests(unittest.TestCase):
    def test_empty_distinguished_from_failure(self):
        repo=Mock()
        repo.read_all.return_value=[]
        service=DashboardService(repo)
        self.assertEqual(service.load('RESET').message,'No matching animal records.')
        repo.read_all.side_effect=RepositoryError('Animal records could not be loaded.')
        self.assertIn('could not',service.load('RESET').message)

    def test_invalid_profile_does_not_read(self):
        repo=Mock()
        result=DashboardService(repo).load('invalid')
        self.assertEqual(result.rows,[])
        repo.read_all.assert_not_called()

    def test_bad_record_becomes_visible_error(self):
        repo=Mock()
        repo.read_all.return_value=[{}]
        self.assertIn('stable id',DashboardService(repo).load('RESET').message)

    def test_json_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'data.json'
            repo=JsonRepository(path)
            with self.assertRaises(RepositoryError): repo.read_all()
            for content in ['{broken','{}']:
                path.write_text(content)
                with self.assertRaises(RepositoryError): repo.read_all()

    def test_mongo_failure_sanitized(self):
        from pymongo.errors import OperationFailure
        client=Mock()
        collection=Mock()
        client.__getitem__=Mock(return_value={'animals':collection})
        repo=MongoRepository(client,'aac','animals')
        # This fake failure checks that private details do not appear in the message or log.
        collection.find.side_effect=OperationFailure('secret connection detail')
        with self.assertLogs('shelter.repository',level='WARNING') as logs:
            with self.assertRaises(RepositoryError) as error: repo.read_all()
        self.assertNotIn('secret',str(error.exception))
        self.assertNotIn('secret',' '.join(logs.output))
        repo.close()
        client.close.assert_called_once()


# Requests through Dash catch callback problems that helper tests can miss.
class DashIntegrationTests(unittest.TestCase):
    # Each test gets a fresh app and mock so results do not depend on test order.
    def setUp(self):
        self.repo=Mock()
        self.repo.read_all.return_value=[animal()]
        self.app=create_app(Settings.from_env({}), self.repo)
        self.client=self.app.server.test_client()

    def test_factory_does_not_read_and_routes_respond(self):
        self.repo.read_all.assert_not_called()
        for path in ['/', '/_dash-layout', '/_dash-dependencies']:
            self.assertEqual(self.client.get(path).status_code,200)

    def test_real_filter_callback_http(self):
        key=next(k for k in self.app.callback_map if 'animals.data' in k)
        response=self.client.post('/_dash-update-component',json={
            'output':key,'outputs':[{'id':'animals','property':'data'},{'id':'status','property':'children'},
                                     {'id':'animals','property':'selected_row_ids'},{'id':'animals','property':'page_current'},
                                     {'id':'animals','property':'sort_by'}],
            'inputs':[{'id':'filter-type','property':'value','value':'WATER'}],
            'state':[], 'changedPropIds':['filter-type.value']})
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        payload=response.get_json()['response']
        self.assertEqual(payload['animals']['data'][0]['id'],'1')
        self.assertEqual(payload['animals']['selected_row_ids'],[])
        self.assertEqual(payload['animals']['page_current'],0)
        self.assertEqual(payload['animals']['sort_by'],[])
        self.assertEqual(payload['animals']['data'][0]['score'],100)

    def test_real_visual_callback_http(self):
        key=next(k for k in self.app.callback_map if 'breeds.figure' in k)
        for rows,ids in [([],[]),([animal()],['1']),([animal()],['missing'])]:
            response=self.client.post('/_dash-update-component',json={
                'output':key,'outputs':[{'id':'breeds','property':'figure'},{'id':'map','property':'children'}],
                'inputs':[{'id':'animals','property':'derived_virtual_data','value':rows},
                          {'id':'animals','property':'selected_row_ids','value':ids}],
                'state':[], 'changedPropIds':['animals.derived_virtual_data']})
            self.assertEqual(response.status_code,200,response.get_data(as_text=True))

    def test_import_has_no_data_access(self):
        # A separate process checks the first import, rather than reusing already imported modules.
        script="from unittest.mock import patch;\nwith patch('pymongo.MongoClient', side_effect=AssertionError('connection at import')):\n import shelter.app\n import run\n"
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__':
    unittest.main()
