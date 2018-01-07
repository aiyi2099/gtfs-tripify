"""
`gtfs-tripify` utilities test module. Asserts that utility functions are correct.
"""

import unittest
import pandas as pd

import sys; sys.path.append("../")
import gtfs_tripify as gt


class TestCutCancellations(unittest.TestCase):
    """
    Tests the cut-cancellation heuristic.
    """
    def setUp(self):
        self.log_columns = ['trip_id', 'route_id', 'action', 'minimum_time', 'maximum_time', 'stop_id',
                            'latest_information_time']

    def test_no_op(self):
        """
        The heuristic should do nothing if the log is empty.
        """
        log = pd.DataFrame(columns=self.log_columns)
        result = gt.utils.cut_cancellations(log)
        assert len(result) == 0

    def test_zero_confirmed(self):
        """
        The heuristic should return an empty log if there are zero confirmed stops in the log.
        """
        log = pd.DataFrame(columns=self.log_columns, data=[['_', '_', 'STOPPED_OR_SKIPPED', '_', '_', '_', '_']])
        result = gt.utils.cut_cancellations(log)
        assert len(result) == 0

    def test_zero_tailing_unconfirmed(self):
        """
        The heuristic should return an unmodified log if there are no tailing `STOPPED_OR_SKIPPED` records.
        """
        log = pd.DataFrame(columns=self.log_columns, data=[['_', '_', 'STOPPED_AT', '_', '_', '_', '_']])
        result = gt.utils.cut_cancellations(log)
        assert len(result) == 1

    def test_one_tailing_unconfirmed(self):
        """
        The heuristic should return an unmodified log if there is one tailing `STOPPED_OR_SKIPPED` record.
        """
        log = pd.DataFrame(columns=self.log_columns,
                           data=[
                               ['_', '_', 'STOPPED_AT', '_', '_', '_', '_'],
                               ['_', '_', 'STOPPED_OR_SKIPPED', '_', '_', '_', '_']
                           ])
        result = gt.utils.cut_cancellations(log)
        assert len(result) == 2

    def test_many_unique_tailing_unconfirmed(self):
        """
        The heuristic should return an unmodified log if there is at least one `STOPPED_AT` record and many
        tailing `STOPPED_OR_SKIPPED` records, but the logs have two or more unique `LATEST_INFORMATION_TIME` values.
        """
        log = pd.DataFrame(columns=self.log_columns,
                           data=[
                               ['_', '_', 'STOPPED_AT', '_', '_', '_', 0],
                               ['_', '_', 'STOPPED_OR_SKIPPED', '_', '_', '_', 0],
                               ['_', '_', 'STOPPED_OR_SKIPPED', '_', '_', '_', 1]
                           ])
        result = gt.utils.cut_cancellations(log)
        assert len(result) == 3

    def test_many_nonunique_tailing_unconfirmed(self):
        """
        The heuristic should return a block-cleaned log if there is at least one `STOPPED_AT` record and many tailing
        `STOPPED_OR_SKIPPED` records, but the logs have just one unique `LATEST_INFORMATION_TIME` values.
        """
        log = pd.DataFrame(columns=self.log_columns,
                           data=[
                               ['_', '_', 'STOPPED_AT', '_', '_', '_', 0],
                               ['_', '_', 'STOPPED_OR_SKIPPED', '_', '_', '_', 1],
                               ['_', '_', 'STOPPED_OR_SKIPPED', '_', '_', '_', 1]
                           ])
        result = gt.utils.cut_cancellations(log)
        assert len(result) == 1


class TestDiscardPartialLogs(unittest.TestCase):
    """
    Tests the partial log heuristic.
    """
    def setUp(self):
        self.log_columns = ['trip_id', 'route_id', 'action', 'minimum_time', 'maximum_time', 'stop_id',
                            'latest_information_time']

    def test_single_discard(self):
        """
        If there's just one record matching the first-or-last `LATEST_INFORMATION_TIME` condition, discard that one.
        """
        first = pd.DataFrame(columns=self.log_columns,
                             data=[
                                 ['_', '_', '_', '_', '_', '_', 0],
                                 ['_', '_', '_', '_', '_', '_', 2]
                             ])
        second = pd.DataFrame(columns=self.log_columns,
                             data=[
                                 ['_', '_', '_', '_', '_', '_', 1]
                             ])
        logbook = {'_0': first, '_1': second}
        result = gt.utils.discard_partial_logs(logbook)
        assert len(result) == 1

    def test_multiple_discard(self):
        """
        If there's more than one record matching the first-or-last `LATEST_INFORMATION_TIME` condition, discard them
        all.
        """
        first = pd.DataFrame(columns=self.log_columns,
                             data=[
                                 ['_', '_', '_', '_', '_', '_', 0],
                                 ['_', '_', '_', '_', '_', '_', 1]
                             ])
        second = pd.DataFrame(columns=self.log_columns,
                              data=[
                                   ['_', '_', '_', '_', '_', '_', 1]
                              ])
        third = pd.DataFrame(columns=self.log_columns,
                             data=[
                                 ['_', '_', '_', '_', '_', '_', 0],
                                 ['_', '_', '_', '_', '_', '_', 2]
                             ])

        logbook = {'_0': first, '_1': second, '_2': third}
        result = gt.utils.discard_partial_logs(logbook)
        assert len(result) == 1