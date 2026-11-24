import ast
import contextlib
import importlib.util
import io
import json
import math
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ab_sample_size', ROOT / 'tools/diagnostics/ab-sample-size-20261124/size.py')
size = importlib.util.module_from_spec(spec)
spec.loader.exec_module(size)


class AbSampleSize(unittest.TestCase):
    def run_main(self, command):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = size.main(command.split())
        return code, out.getvalue(), err.getvalue()

    def test_worse_limit_and_binom(self):
        self.assertEqual([size.worse_limit(m) for m in (0, 5, 6, 8, 9)], [-1, -1, 0, 0, 1])
        exact, got = math.comb(3000, 1500) / 2 ** 3000, size.binom(3000, .5)
        self.assertEqual(len(got), 3001)
        self.assertLessEqual(abs(got[1500] - exact) / exact, 1e-9)
        self.assertAlmostEqual(math.fsum(got), 1, delta=1e-9)
        self.assertEqual(size.binom(5, 0), [1, 0, 0, 0, 0, 0])
        self.assertEqual(size.binom(5, 1), [0, 0, 0, 0, 0, 1])

    def test_power(self):
        brute = []
        for b in range(13):
            for c in range(13 - b):
                m = b + c
                p = min(1, 2 * sum(math.comb(m, k) for k in range(min(b, c) + 1)) / 2 ** m)
                if p < .05 and c > b:
                    brute.append(math.comb(12, m) * math.comb(m, b) * .1 ** b * .3 ** c * .6 ** (12 - m))
        self.assertGreater(len(brute), 0)
        self.assertAlmostEqual(size.power_curve(.1, .3, 12)[12], math.fsum(brute), delta=1e-12)
        tail = math.fsum(math.comb(81, k) * .0556 ** k * .9444 ** (81 - k) for k in range(6))
        self.assertAlmostEqual(size.power_curve(0, .0556, 81)[81], 1 - tail, delta=1e-12)
        for n, pb, pc, expected in [(81, 0, .0556, .2951719894379349), (300, .0185, .0741, .8754797777879639),
                                    (500, .0185, .0556, .8439360087519838), (200, 0, .0333, .6577218641091224)]:
            with self.subTest(n=n):
                self.assertAlmostEqual(size.power_curve(pb, pc, n)[n], expected, delta=1e-9)
        for pb in (0, .02):
            self.assertEqual(size.power_curve(pb, 0, 50), [0.] * 51)
        got = size.power_curve(.3, .3, 2000)[2000]  # underflow regression: a recurrence from (1-p)**n gives 0.0
        self.assertTrue(.02 < got < .025, got)

    def test_need(self):
        for pb, pc, cards in [(0, .0556, 141), (.0185, .0741, 249), (.0185, .0556, 454), (0, .0333, 236)]:
            with self.subTest(pb=pb, pc=pc):
                code, out, _ = self.run_main(f'need {pb} {pc}')
                report = json.loads(out)
                self.assertEqual((code, report['cards']), (0, cards))
                curve = size.power_curve(pb, pc, cards + 50)
                self.assertEqual(report['min_power_in_window'], min(curve[cards:]))
                self.assertGreaterEqual(report['min_power_in_window'], .8)
                self.assertLess(min(curve[cards - 1:cards + 50]), .8)
        code, out, _ = self.run_main('need 0.02 0.02')
        report = json.loads(out)
        self.assertEqual((code, report['cards'], report['min_power_in_window']), (0, None, None))

    def test_tango_and_pass_fixed(self):
        for args, z in [((0, 0, 175, .02), -math.sqrt(175 * .02 / .98)), ((3, 1, 100, .02), 0), ((6, 0, 300, .02), 0),
                        ((5, 5, 100, .1), -10 / math.sqrt(100 * (2 * (math.sqrt(460) - 10) / 400 + .09)))]:
            with self.subTest(args=args):
                self.assertAlmostEqual(size.tango_z(*args), z, delta=1e-12)
        for n, delta, pb, pc, expected in [
                (175, .02, 0, 0, 1.), (100, .02, 0, 0, 0.), (175, .05, .0286, .0286, .8052555314172499),
                (500, .03, .02, .02, .9372101405194476), (1000, .02, .01, .01, .9934027452382349),
                (300, .02, .02, 0, .060183697890572964), (175, .05, .05, 0, .05940224780322603),
                (500, .03, .04, .01, .04841558076061227)]:
            with self.subTest(n=n, delta=delta, pb=pb):
                self.assertAlmostEqual(size.pass_probability(n, delta, [(pb, pc)])[0], expected, delta=1e-9)
        tail = math.fsum(math.comb(300, k) * .02 ** k * .98 ** (300 - k) for k in range(3))
        self.assertAlmostEqual(size.pass_probability(300, .02, [(.02, 0)])[0], tail, delta=1e-9)

    def test_false_pass(self):
        code, out, _ = self.run_main('noninferior 300 0.02 0.02 0')
        got = json.loads(out)['false_pass']
        self.assertEqual(code, 0)
        self.assertAlmostEqual(got['by_pc']['0'], .060183697890572964, delta=1e-9)
        self.assertEqual((got['max'], got['at_pc']), (got['by_pc']['0'], 0))
        self.assertEqual(list(got['by_pc']), ['0', '0.001', '0.002', '0.005', '0.01', '0.02', '0.03', '0.05'])
        code, out, _ = self.run_main('noninferior 300 0.02 0.02 0 --crit 1.65')
        report = json.loads(out)
        tail = math.fsum(math.comb(300, k) * .02 ** k * .98 ** (300 - k) for k in range(2))
        self.assertEqual(code, 0)
        self.assertAlmostEqual(report['pass_probability'], tail, delta=1e-12)
        self.assertLessEqual(report['false_pass']['max'], .05)

    def test_cli_bad_input_and_structure(self):
        for command in ('power 20 0 0.1', 'need 0 0.3 --max-n 60 --window 5', 'noninferior 20 0.2 0.1 0.1'):
            with self.subTest(command=command), mock.patch('builtins.open', side_effect=AssertionError('file access')):
                code, out, err = self.run_main(command)
                report = json.loads(out)
                self.assertEqual((code, err, report['command']), (0, '', command.split()[0]))
                self.assertEqual((report['notes'], len(report['notes'])), (size.NOTES, 3))
                for word in ('합격', '채택', '충분', '권고'):
                    self.assertNotIn(word, out)
        for command in ('power 0 0 0.1', 'power 10 0.6 0.4', 'noninferior 100 0 0 0', 'noninferior 2001 0.02 0 0',
                        'need 0 0.05 --max-n 5001', 'need 0 0.05 --target 1', 'noninferior 100 0.02 0 0 --crit 0'):
            with self.subTest(command=command):
                code, out, err = self.run_main(command)
                self.assertEqual((code, out, len(err.splitlines())), (2, '', 1))
        nodes = list(ast.walk(ast.parse(Path(size.__file__).read_text())))
        self.assertEqual(sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for n in nodes), 7)


if __name__ == '__main__':
    print('size.py:', size.__file__)
    unittest.main()
