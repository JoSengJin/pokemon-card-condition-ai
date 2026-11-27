"""Review 2026-11-27 I-2, I-3 (and the NaN ppm minor): the exact inputs that passed silently."""
import contextlib
import hashlib
import io
import json
import unittest

from tests.test_zone_rows import LINE, ZoneBase
from tools import zone_rows


class ZoneRowsRejectTest(ZoneBase):
    def test_bad_provenance_never_turns_into_rows(self):
        (self.root / 'answers.txt').write_text(LINE, encoding='utf-8')
        digest = hashlib.sha256(LINE.encode()).hexdigest()
        before, zone_rows.backs = zone_rows.backs, lambda intakes: self.info
        self.addCleanup(setattr, zone_rows, 'backs', before)
        for number, bad in enumerate((dict(verdict='ai-identical', answer_sha256=digest), dict(verdict='human', answer_sha256=digest),
                                      dict(verdict='unknown'), {}, [], None, 0)):
            with self.subTest(bad=bad), contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                (self.root / 'prov.json').write_text(json.dumps(bad))
                code = zone_rows.main([str(self.root / 'answers.txt'), '--kind', 'corner', '--box', 'confirmed-only',
                                       '--out', str(self.root / f'out{number}'), '--provenance', str(self.root / 'prov.json')])
                self.assertEqual((code, (self.root / f'out{number}').exists()), (2, False))

    def test_only_back_side_answers_are_accepted(self):
        for side in ('front', 'zzz'):
            with self.subTest(side=side), self.assertRaisesRegex(ValueError, '1번째 줄'):
                zone_rows.parse(LINE.replace('/back=', f'/{side}='))

    def test_unusable_ppm_is_refused(self):
        rows, _ = self.build()
        key = f"{rows[0]['id']}|{rows[0]['image_sha256']}|{','.join(f'{v:.6f}' for v in rows[0]['box'])}"
        for ppm in (float('nan'), float('inf'), -1, '12'):
            with self.subTest(ppm=ppm), self.assertRaises(ValueError):
                zone_rows.facts(rows, {key: dict(status='ok', ppm=ppm)})


if __name__ == '__main__':
    unittest.main()
