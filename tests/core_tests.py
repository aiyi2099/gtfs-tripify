"""
`gtfs-tripify` core test module. Asserts that all data generation steps are correct.
"""

import unittest
import pytest
from google.transit import gtfs_realtime_pb2

import collections
import numpy as np
import pandas as pd

import sys; sys.path.append("../")
import gtfs_tripify as gt


class TestDictify(unittest.TestCase):
    def setUp(self):
        with open("./fixtures/gtfs-20160512T0400Z", "rb") as f:
            gtfs = gtfs_realtime_pb2.FeedMessage()
            gtfs.ParseFromString(f.read())

        self.gtfs = gtfs

    def test_dictify(self):
        feed = gt.dictify(self.gtfs)
        assert set(feed) == {'entity', 'header'}
        assert feed['header'].keys() == {'timestamp', 'gtfs_realtime_version'}
        assert isinstance(feed['header']['timestamp'], int)
        assert(dict(collections.Counter([message['type'] for message in feed['entity']]))) == {'alert': 1,
                                                                                               'trip_update': 94,
                                                                                               'vehicle_update': 68}
        assert len(feed['entity']) == 1 + 94 + 68

        assert feed['entity'][-1]['type'] == 'alert'
        assert set(feed['entity'][-1]['alert']['informed_entity'][0].keys()) == {'route_id', 'trip_id'}

        assert feed['entity'][-2]['type'] == 'trip_update'
        assert len(feed['entity'][-2]['trip_update']['stop_time_update']) == 2
        assert set(feed['entity'][-2]['trip_update']['stop_time_update'][0].keys()) == {'arrival', 'departure',
                                                                                        'stop_id'}

        assert feed['entity'][5]['type'] == 'vehicle_update'
        assert set(feed['entity'][5]['vehicle'].keys()) == {'trip', 'stop_id', 'timestamp', 'current_stop_sequence',
                                                            'current_status'}


class TestActionify(unittest.TestCase):
    def test_case_1(self):
        """
        The train is STOPPED_AT a station somewhere along the route. The train is not expected to skip any of the
        stops along the route.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463026080, 'departure': 1463026080, 'stop_id': '103S'},
                    {'arrival': 1463026170, 'departure': 1463026170, 'stop_id': '104S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'STOPPED_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['STOPPED_AT', 'EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT',
                                       'EXPECTED_TO_ARRIVE_AT']

    def test_case_2(self):
        """
        The train is currently IN_TRANSIT_TO a station somewhere along the route. The train is not expected to skip
        any of the stops along the route.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463026080, 'departure': 1463026080, 'stop_id': '103S'},
                    {'arrival': 1463026170, 'departure': 1463026170, 'stop_id': '104S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'IN_TRANSIT_TO',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT', 'EXPECTED_TO_ARRIVE_AT',
                                       'EXPECTED_TO_DEPART_AT', 'EXPECTED_TO_ARRIVE_AT']

    def test_case_3(self):
        """
        The train is currently INCOMING_AT a station somewhere along the route. This case is treated the same was as
        the case above.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463026080, 'departure': 1463026080, 'stop_id': '103S'},
                    {'arrival': 1463026170, 'departure': 1463026170, 'stop_id': '104S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT', 'EXPECTED_TO_ARRIVE_AT',
                                       'EXPECTED_TO_DEPART_AT', 'EXPECTED_TO_ARRIVE_AT']

    def test_case_4(self):
        """
        The train is queued. The train is not expected to skip any of the stops along the route.

        Every station except for the first and last has an EXPECTED_TO_ARRIVE_AT and
        EXPECTED_TO_DEPART_AT entry. The last only has an EXPECTED_TO_ARRIVE_AT entry. The first only has an
        EXPECTED_TO_DEPART_AT entry.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': np.nan, 'departure': 1463026080, 'stop_id': '103S'},
                    {'arrival': 1463026170, 'departure': 1463026170, 'stop_id': '104S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, None, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_DEPART_AT', 'EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT',
                                       'EXPECTED_TO_ARRIVE_AT']

    def test_case_5(self):
        """
        The train is currently INCOMING_AT the final stop on its route.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '140S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_ARRIVE_AT']

    def test_case_6(self):
        """
        The train is currently IN_TRANSIT_TO the final stop on its route.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'IN_TRANSIT_TO',
                'current_stop_sequence': 34,
                'stop_id': '140S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_ARRIVE_AT']

    def test_case_7(self):
        """
        The train is currently STOPPED_AT the final stop on its route.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'STOPPED_AT',
                'current_stop_sequence': 34,
                'stop_id': '140S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['STOPPED_AT']

    def test_case_8(self):
        """
        The train is somewhere along its trip, and follows all of the same rules as the similar earlier test cases
        thereof. However, it is also expected to skip one or more stops along its route.

        There are actually two such cases. In the first case, we have an intermediate station with only a departure.
        In the second, an intermediate station with only an arrival.

        One hopes that there isn't some special meaning attached to the difference between the two.
        """
        # First subcase.
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463026080, 'departure': 1463026080, 'stop_id': '103S'},
                    {'arrival': 1463026170, 'departure': np.nan, 'stop_id': '104S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT', 'EXPECTED_TO_SKIP',
                                       'EXPECTED_TO_ARRIVE_AT']

        # Second subcase.
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463026080, 'departure': 1463026080, 'stop_id': '103S'},
                    {'arrival': np.nan, 'departure': 1463026170, 'stop_id': '104S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT', 'EXPECTED_TO_SKIP',
                                       'EXPECTED_TO_ARRIVE_AT']

    def test_case_9(self):
        """
        The train is expected to skip the first stop along its route.
        """
        # First subcase.
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': np.nan, 'departure': 1463026080, 'stop_id': '103S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT']

        # Second subcase.
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': '000650_1..S02R'},
                'stop_time_update': [
                    {'arrival': 1463026080, 'departure': np.nan, 'stop_id': '103S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        timestamp = 1463025417

        log = gt.actionify(trip_message, vehicle_message, timestamp)
        assert list(log['action']) == ['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT']


class TestCorrectFeed(unittest.TestCase):
    def test_vehicle_update_only(self):
        """
        Assert that we raise a warning and remove the entry with `correct` when a trip only have a vehicle warning
        in the feed.
        """
        trip_message = {
            'id': '000001',
            'type': 'trip_update',
            'trip_update': {
                'trip': {'route_id': '1',
                         'start_date': '20160512',
                         'trip_id': ''},
                'stop_time_update': [
                    {'arrival': 1463026080, 'departure': np.nan, 'stop_id': '103S'},
                    {'arrival': 1463029500, 'departure': np.nan, 'stop_id': '140S'}
                ]
            }
        }
        vehicle_message = {
            'id': '000006',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': ''
                }
            }
        }
        feed = {
            'header': {'gtfs_realtime_version': 1,
                       'timestamp': 1463025417},
            'entity': [trip_message, vehicle_message]
        }

        # noinspection PyUnresolvedReferences
        with pytest.warns(UserWarning):
            feed = gt.correct(feed)

        assert len(feed['entity']) == 0

    def test_empty_trip_id(self):
        """
        Assert that we raise a warning and remove the entry with `correct` when a feed entity has a null trip_id.
        """
        vehicle_message = {
            'id': '',
            'type': 'vehicle_update',
            'vehicle': {
                'current_status': 'INCOMING_AT',
                'current_stop_sequence': 34,
                'stop_id': '103S',
                'timestamp': 1463025417,
                'trip': {
                    'route_id': '1',
                    'start_date': '20160511',
                    'trip_id': '137100_1..N02X017'
                }
            }
        }
        feed = {
            'header': {'gtfs_realtime_version': 1,
                       'timestamp': 1463025417},
            'entity': [vehicle_message]
        }

        # noinspection PyUnresolvedReferences
        with pytest.warns(UserWarning):
            feed = gt.correct(feed)

        assert len(feed['entity']) == 0

    def test_empty_trip_id_2(self):
        feed = {'header': {'timestamp': 1},
                'entity': [{'id': '000022',
                            'type': 'vehicle_update',
                            'vehicle': {'current_stop_sequence': 0,
                                        'stop_id': '',
                                        'current_status': 'IN_TRANSIT_TO',
                                        'timestamp': 0,
                                        'trip': {'route_id': '',
                                                 'trip_id': '',
                                                 'start_date': ''}}}]}
        # noinspection PyUnresolvedReferences
        with pytest.warns(UserWarning):
            feed = gt.correct(feed)

        assert len(feed['entity']) == 0


def create_mock_action_log(actions=None, stops=None, information_time=0):
    length = len(actions)
    return pd.DataFrame({
        'trip_id': ['TEST'] * length,
        'route_id': [1] * length,
        'action': actions,
        'stop_id': ['999X'] * length if stops is None else stops,
        'information_time': [information_time] * length,
        'time_assigned': list(range(length))
    })


class TripLogUnaryTests(unittest.TestCase):
    """
    Tests for simpler cases which can be processed in a single action log.
    """

    def test_unary_stopped(self):
        """
        An action log with just a stoppage ought to report as a trip log with just a stoppage.
        """
        actions = [create_mock_action_log(['STOPPED_AT'])]
        result = gt.tripify(actions)

        assert len(result) == 1
        assert result.iloc[0].action == 'STOPPED_AT'
        assert all([str(result.iloc[0]['maximum_time']) == 'nan', str(result.iloc[0]['minimum_time']) == 'nan',
                    int(result.iloc[0]['latest_information_time']) == 0])

    def test_unary_en_route(self):
        """
        An action log with just an arrival and departure ought to report as just an arrival (note: this is the same
        technically broken case tested by the eight test in action log testing; for more on when this arises,
        check the docstring there).
        """
        actions = [create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT'])]
        result = gt.tripify(actions)

        assert len(result) == 1
        assert result.iloc[0].action == 'EN_ROUTE_TO'
        assert all([result.iloc[0]['maximum_time'] in [np.nan, 'nan'],
                    int(result.iloc[0]['minimum_time']) == 0,
                    int(result.iloc[0]['latest_information_time']) == 0])

    def test_unary_end(self):
        """
        An action log with a single arrival ought to report a single EN_ROUTE_TO in the trip log.
        """
        result = gt.tripify([
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT'])
        ])
        assert len(result) == 1
        assert result.iloc[0].action == 'EN_ROUTE_TO'
        assert all([result.iloc[0]['maximum_time'] in [np.nan, 'nan'],
                    int(result.iloc[0]['minimum_time']) == 0,
                    int(result.iloc[0]['latest_information_time']) == 0])

    def test_unary_arriving_skip(self):
        """
        An action log with a stop to be skipped ought to report an arrival at that stop in the resultant trip log.
        This is because we leave the job of detecting a skip to the combination process.

        This is an "arriving skip" because a skip will occur on a station that has either a departure or arrival
        defined, but not both.
        """
        actions = [
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART',
                                            'EXPECTED_TO_ARRIVE_AT'], stops=['999X', '998X', '998X', '997X'])
        ]
        result = gt.tripify(actions)

        assert len(result) == 3
        assert list(result['action'].values) == ['EN_ROUTE_TO', 'EN_ROUTE_TO', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [0] * 3
        assert list(result['maximum_time'].values.astype(str)) == ['nan'] * 3

    def test_unary_departing_skip(self):
        """
        An action log with a stop to be skipped ought to report an arrival at that stop in the resultant trip log.
        This is because we leave the job of detecting a skip to the combination process.

        This is an "arriving skip" because a skip will occur on a station that has either a departure or arrival
        defined, but not both.
        """
        actions = [
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART', 'EXPECTED_TO_DEPART',
                                            'EXPECTED_TO_ARRIVE_AT'], stops=['999X', '998X', '998X', '997X'])
        ]
        result = gt.tripify(actions)

        assert len(result) == 3
        assert list(result['action'].values) == ['EN_ROUTE_TO', 'EN_ROUTE_TO', 'EN_ROUTE_TO']
        assert result['action'].values.all() == 'EN_ROUTE_TO'
        assert list(result['minimum_time'].values.astype(int)) == [0] * 3
        assert list(result['maximum_time'].values.astype(str)) == ['nan'] * 3

    def test_unary_en_route_trip(self):
        """
        A slightly longer test. Like `test_unary_en_route`, but with a proper station terminus.
        """
        actions = [
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_FROM',
                                            'EXPECTED_TO_ARRIVE_AT'],
                                   stops=['999X', '999X', '998X'])
        ]
        result = gt.tripify(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['EN_ROUTE_TO', 'EN_ROUTE_TO']
        assert result['action'].values.all() == 'EN_ROUTE_TO'
        assert list(result['minimum_time'].values.astype(int)) == [0] * 2
        assert list(result['maximum_time'].values.astype(str)) == ['nan'] * 2

    def test_unary_ordinary_stopped_trip(self):
        """
        A slightly longer test. Like `test_unary_stopped`, but with an additional arrival after the present one.
        """
        actions = [
            create_mock_action_log(actions=['STOPPED_AT', 'EXPECTED_TO_ARRIVE_AT'],
                                   stops=['999X', '998X'])
        ]
        result = gt.tripify(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_AT', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(str)) == ['nan', '0']
        assert list(result['maximum_time'].values.astype(str)) == ['nan', 'nan']


class TripLogBinaryTests(unittest.TestCase):
    """
    Tests for more complicated cases necessitating both action logs.

    These tests do not invoke station list changes between action logs, e.g. they do not address reroutes.
    """

    def test_binary_en_route(self):
        """
        In the first observation, the train is EN_ROUTE to a station. In the next observation, it is still EN_ROUTE
        to that station.

        Our output should be a trip log with a single row. Critically, the minimum_time recorded should correspond
        with the time at which the second observation was made---1, in this test case.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '999X'])
        first = base.head(1)
        second = base.tail(1).set_value(1, 'information_time', 1)
        actions = [first, second]

        result = gt.tripify(actions)

        assert len(result) == 1
        assert list(result['action'].values) == ['EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [1]
        assert list(result['maximum_time'].values.astype(str)) == ['nan']

    def test_binary_en_route_stop(self):
        """
        In the first observation, the train is EN_ROUTE to a station. In the next observation, it STOPPED_AT that
        station.

        Our output should be a trip log with a single row, recording the time at which the stop was made.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'STOPPED_AT'],
                                      stops=['999X', '999X'])
        first = base.head(1)
        second = base.tail(1).set_value(1, 'information_time', 1)
        actions = [first, second]

        result = gt.tripify(actions)

        assert len(result) == 1
        assert list(result['action'].values) == ['STOPPED_AT']
        assert list(result['minimum_time'].values.astype(int)) == [0]
        assert list(result['maximum_time'].values.astype(str)) == ['nan']

    def test_binary_stop_or_skip_en_route(self):
        """
        In the first observation, the train is EN_ROUTE to a station. In the next observation, it is EN_ROUTE to
        a different station, one further along in the record.

        Our output should be a trip log with two rows, one STOPPED_OR_SKIPPED at the first station,
        and one EXPECTED_TO_ARRIVE_AT in another.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT',
                                               'EXPECTED_TO_ARRIVE_AT',
                                               'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '999X', '998X', '998X'])
        first = base.head(3)
        second = base.tail(1).set_value(3, 'information_time', 1)
        actions = [first, second]

        result = gt.tripify(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [0, 1]
        assert list(result['maximum_time'].values.astype(str)) == ['1', 'nan']

    def test_binary_skip_en_route(self):
        """
        In the first observation, the train is EN_ROUTE to a station which it is going to skip. In the second
        observation the train is en route to another station further down the line.

        Our output should be a trip log with two rows. The first entry should be a STOPPED_OR_SKIPPED at the first
        station, and then the second should be an EN_ROUTE_TO at the second station.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT',
                                               'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '998X', '998X'])
        first = base.head(2)
        second = base.tail(1).set_value(2, 'information_time', 1)
        actions = [first, second]

        result = gt.tripify(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [0, 1]
        assert list(result['maximum_time'].values.astype(str)) == ['1', 'nan']

    def test_binary_skip_stop(self):
        """
        In the first observation, the train is EN_ROUTE to a station which it is going to skip. In the second
        observation the train is stopped at another station further down the line.

        Our output should be a trip log with two rows. The first entry should be a STOPPED_OR_SKIPPED at the first
        station, and then the second should be a STOPPED_AT at the second station.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT',
                                               'STOPPED_AT'],
                                      stops=['999X', '998X', '998X'])
        first = base.head(2)
        second = base.tail(1).set_value(2, 'information_time', 1)
        actions = [first, second]

        result = gt.tripify(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'STOPPED_AT']
        assert list(result['minimum_time'].values.astype(int)) == [0, 0]
        assert list(result['maximum_time'].values.astype(str)) == ['1', 'nan']


class TripLogReroutingTests(unittest.TestCase):
    """
    These tests make sure that trip logs work as expected when the train gets rerouted.
    """
    def test_en_route_reroute(self):
        """
        Behavior when en route, and rerouted to another en route, is that the earlier station(s) ought to be marked
        "STOPPED_OR_SKIPPED".
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '998X'])
        first = base.head(1)
        second = base.tail(1).set_value(1, 'information_time', 1)

        result = gt.tripify([first, second])

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'EN_ROUTE_TO']


class TripLogFinalizationTests(unittest.TestCase):
    """
    Tests for finalization.

    Within the GTFS-Realtime log, a signal that a train trip is complete only comes in the form of that trip's
    messages no longer appearing in the queue in the next update. The most recently recorded message may be in any
    conceivable state prior to this occurring. Finalization is the procedure "capping off" any still to-be-arrived-at
    stations. Since this involves contextual knowledge about records appearing and not appearing in the data stream,
    this procedure is provided as a separate method.

    These tests ascertain that said method, `_finish_trip`, works as advertised.

    NB: it's easier to test this using this internal method because the requisite forward-facing method relies on the
    Google protobuf wrapper library, which produces objects that are neither constructable nor mutable.
    """
    def test_finalize_no_op(self):
        """
        Finalization should do nothing to trip logs that are already complete.
        """
        base = create_mock_action_log(actions=['STOPPED_AT'], stops=['999X'])
        result = gt.tripify([base], finished=True, finish_information_time=np.nan)

        assert len(result) == 1
        assert list(result['action'].values) == ['STOPPED_AT']

    def test_finalize_en_route(self):
        """
        Finalization should cap off trips that are still EN_ROUTE.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT'], stops=['999X'])
        result = gt.tripify([base], finished=True, finish_information_time=np.nan)

        assert len(result) == 1
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED']

    def test_finalize_all(self):
        """
        Make sure that finalization works across columns as well.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT'], stops=['999X', '998X'])
        first = base.head(1)
        second = base.tail(1)
        result = gt.tripify([first, second], finished=True, finish_information_time=42)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'STOPPED_OR_SKIPPED']
        assert list(result['maximum_time'].astype(int).values) == [42, 42]


class TripLogbookTests(unittest.TestCase):
    """
    Smoke tests for generating trip logbooks and merging them.
    """
    def setUp(self):
        with open("./fixtures/gtfs-20160512T0400Z", "rb") as f:
            gtfs_0 = gtfs_realtime_pb2.FeedMessage()
            gtfs_0.ParseFromString(f.read())

        with open("./fixtures/gtfs-20160512T0401Z", "rb") as f:
            gtfs_1 = gtfs_realtime_pb2.FeedMessage()
            gtfs_1.ParseFromString(f.read())

        # with open("./data/example_tripwise_action_logs.p", "rb") as f:
        #     self.tripwise = pickle.load(f)

        self.log_0 = gt.dictify(gtfs_0)
        self.log_1 = gt.dictify(gtfs_1)

    # This test no longer works because a change in the pandas library has rendered the pickle used for this test,
    # "example_tripwise_action_logs.p", incompatible with recent versions of pandas. In the future do not rely on the
    # pickle module to preserve your data!
    # TODO: replace this test.
    # def test_tripify_schema(self):
    #     """
    #     Assert that the result of tripifying an example tripwise action log pulled from real data has approximately
    #     the schematic result that we expect.
    #     """
    #     result = gt.tripify(self.tripwise, finished=True, finish_information_time=1463028093)
    #
    #     assert list(result['stop_id'][-3:].values) == ['L27S', 'L28S', 'L29S']
    #     assert list(result['action'][-3:].values) == ['STOPPED_AT', 'STOPPED_AT', 'STOPPED_OR_SKIPPED']
    #     assert list(result['minimum_time'][-3:].astype(float).values) == [1463027913.0, 1463027973.0, 1463028033.0]
    #     assert list(result['maximum_time'][-3:].astype(float).values) == [1463028033.0, 1463028093.0, 1463028093.0]

    def test_logbook(self):
        logbook = gt.logify([self.log_0, self.log_1])

        assert len(logbook) == 94
