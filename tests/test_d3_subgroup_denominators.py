import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/diagnostics/d3-subgroup-denominators-20261118'))
import subgroups  # noqa: E402

META = {
    'a': dict(query='pokemon card expedition raw', back_size=[1259, 900]),
    'b': dict(query='pokemon card charizard raw', back_size=[1500, 2000]),
    'c': dict(query='pokemon card mew raw', back_size=[1200, 1600]),
}


class SubgroupTest(unittest.TestCase):
    def test_buckets_use_back_short_side_with_half_open_edges(self):
        self.assertEqual([subgroups.bucket([1259, 999]), subgroups.bucket([1000, 2000]), subgroups.bucket([1499, 2000]), subgroups.bucket([1500, 1501])],
                         ['<1000', '1000-1499', '1000-1499', '>=1500'])

    def test_query_group_separates_set_queries_from_character_queries(self):
        self.assertEqual([subgroups.query_group('pokemon card hidden fates raw'), subgroups.query_group('pokemon card base set 2 raw'),
                          subgroups.query_group('pokemon card pikachu raw')], ['set', 'set', 'character'])

    def test_tally_counts_positive_and_normal_objects_per_subgroup_and_reports_unmatched(self):
        objects = {'a': True, 'b': False, 'c': False, 'zz': True}
        got = subgroups.tally(objects, META)
        self.assertEqual(got['bucket']['<1000'], dict(positive=1, normal=0))
        self.assertEqual(got['bucket']['>=1500'], dict(positive=0, normal=1))
        self.assertEqual(got['bucket']['1000-1499'], dict(positive=0, normal=1))
        self.assertEqual(got['query_group']['set'], dict(positive=1, normal=0))
        self.assertEqual(got['query_group']['character'], dict(positive=0, normal=2))
        self.assertEqual(got['unmatched'], dict(positive=1, normal=0))


if __name__ == '__main__':
    unittest.main()
