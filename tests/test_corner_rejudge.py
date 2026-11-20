import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows(n_groups=80):
    return [dict(id=f'g{g}/{a}', group=f'g{g}', area=a, target=int((g + k) % 2 == 0), image='x', box=[0, 0, .3, .3])
            for g in range(n_groups) for k, a in enumerate(['upper_left', 'upper_right'])]


class SelectTest(unittest.TestCase):
    def test_60_zones_30_each_one_per_group_deterministic(self):
        sel = load('tools/relabel_corner_blind_pages.py', 'blind').select
        a, b = sel(rows()), sel(rows())
        self.assertEqual(a, b)
        self.assertEqual(60, len(a))
        self.assertEqual(60, len({z['group'] for z in a}))
        self.assertEqual(30, sum(z['target'] for z in a))

    def test_selection_ignores_any_score_field(self):
        sel = load('tools/relabel_corner_blind_pages.py', 'blind').select
        scored = [dict(r, score=.5) for r in rows()]
        self.assertEqual([z['id'] for z in sel(rows())], [z['id'] for z in sel(scored)])


class ScoreTest(unittest.TestCase):
    def test_parse_and_decision(self):
        s = load('tools/diagnostics/corner-rejudge-20261121/score.py', 'score')
        sel = [dict(n=i, target=int(i <= 30)) for i in range(1, 61)]
        # 6 of 60 flip (3 each way): d = .1 -> f ~ .0528
        ans = {i: ('결함' if i <= 30 else '정상') for i in range(1, 61)}
        for i in (1, 2, 3, 31, 32, 33):
            ans[i] = '정상' if i <= 30 else '결함'
        text = '\n'.join(f'z{i}={v}' for i, v in ans.items())
        res = s.score(sel, s.parse(text))
        self.assertEqual((60, 6), (res['used'], res['disagree']))
        self.assertAlmostEqual(.1, res['d'])
        self.assertAlmostEqual(.0528, res['f'], places=3)
        self.assertIn(res['decision'], ('independent_data', 'label_definition', 'undetermined'))

    def test_unknown_is_excluded_not_filled(self):
        s = load('tools/diagnostics/corner-rejudge-20261121/score.py', 'score2')
        sel = [dict(n=i, target=1) for i in range(1, 11)]
        res = s.score(sel, s.parse('\n'.join(f'z{i}=' + ('불가' if i <= 4 else '결함') for i in range(1, 11))))
        self.assertEqual((6, 4), (res['used'], res['unknown']))

    def test_high_flip_recommends_label_definition(self):
        s = load('tools/diagnostics/corner-rejudge-20261121/score.py', 'score3')
        sel = [dict(n=i, target=1) for i in range(1, 61)]
        res = s.score(sel, s.parse('\n'.join(f'z{i}=' + ('정상' if i <= 18 else '결함') for i in range(1, 61))))
        self.assertEqual('label_definition', res['decision'])


class HiresTest(unittest.TestCase):
    def test_pick_unknown_and_defect_to_normal_only(self):
        hi = load('tools/relabel_corner_highres_pages.py', 'hires')
        sel = [dict(n=1, target=1), dict(n=2, target=0), dict(n=3, target=1), dict(n=4, target=0), dict(n=5, target=1)]
        ans = {1: '결함', 2: '정상', 3: '정상', 4: '불가', 5: '불가'}
        self.assertEqual([3, 4, 5], [z['n'] for z in hi.pick(sel, ans)])

    def test_crop_is_larger_than_thumbnail_and_page_hides_labels(self):
        import base64, io, tempfile
        from PIL import Image
        hi = load('tools/relabel_corner_highres_pages.py', 'hires2')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'a.png'
            Image.new('RGB', (3000, 2000), (120, 120, 120)).save(path)
            z = dict(n=7, target=1, image=str(path), box=[0, 0, .3, .3], group='g', area='upper_left')
            width = Image.open(io.BytesIO(base64.b64decode(hi.crop(z)))).size[0]
            html = hi.page(1, 1, [z])
        self.assertGreater(width, 420)
        self.assertIn('data-id="z7"', html)
        self.assertNotIn('target', html)


class ReproTest(unittest.TestCase):
    def test_excludes_previous_groups_and_is_balanced(self):
        rp = load('tools/relabel_corner_repro_pages.py', 'repro')
        sel = rp.select(rows(), {'g0', 'g1', 'g2'})
        self.assertEqual(60, len(sel))
        self.assertFalse({'g0', 'g1', 'g2'} & {z['group'] for z in sel})
        self.assertEqual(30, sum(z['target'] for z in sel))
        self.assertEqual(list(range(1, 61)), [z['n'] for z in sel])

    def test_instruction_states_current_strict_criterion(self):
        rp = load('tools/relabel_corner_repro_pages.py', 'repro2')
        self.assertIn('미세한 백화', rp.INSTRUCTIONS)
        self.assertIn('확대', rp.INSTRUCTIONS)


class ConsensusTest(unittest.TestCase):
    def test_excludes_judged_ids_and_balances_classes(self):
        cs = load('tools/relabel_corner_consensus_pages.py', 'cons')
        cs.PER_CLASS = 50
        rs = rows(80)
        sel = cs.select(rs, {'g0/upper_left', 'g1/upper_left'})
        self.assertEqual(100, len(sel))
        self.assertEqual(50, sum(z['target'] for z in sel))
        self.assertFalse({'g0/upper_left', 'g1/upper_left'} & {z['id'] for z in sel})
        self.assertEqual(len(sel), len({z['id'] for z in sel}))


if __name__ == '__main__':
    unittest.main()
