"""Independent review of 4a2ecc8 (2026-11-28): kept evidence, unreadable AI entries, two cards on one line."""
import os
import unittest

from tests.test_rater_gate import RaterGateBase, text
from tools import rater_gate

AREAS = [f'c{n}' for n in range(9)]
STATES = ['정상', '결함', '정상', '정상', '결함', '정상', '정상', '정상', '결함']


def card(states, name='a'):
    return f'{name}/back=확인;box:0,0,1,1;' + ';'.join(f'{a}:{s}' for a, s in zip(AREAS, states))


class RaterGateReviewTest(RaterGateBase):
    def confirmed(self):
        (self.root / 'said.txt').write_text('직접 판정', encoding='utf-8')
        self.ai('unrelated.txt', ['x'] * 64)
        return ['--statement', str(self.root / 'said.txt'), '--expected', str(self.root / 'said.txt')]

    def test_one_bad_phone_zone_keeps_the_rest_of_the_line(self):
        self.answer.write_text(card(STATES) + '\n', encoding='utf-8')
        for body, verdict, count in ((card(STATES) + ';', 'ai_identical', (9, 9)),
                                     (card(STATES).replace('c3:정상', 'c3:결함:흐림'), 'ai_suspect', (8, 9)),
                                     (card(STATES).replace('c3:정상', 'c3'), 'ai_suspect', (8, 9))):
            with self.subTest(body=body[-30:]):
                (self.root / 'ai-responses/ai.txt').write_text(body + '\n', encoding='utf-8')
                result = self.run_gate()[1]
                found = [(r['matches'], r['total']) for r in result['comparisons']]
                self.assertEqual((result['verdict'], found, result['comparison_complete']), (verdict, [count], False))

    def test_unreadable_ai_entries_block_no_match_and_keep_other_evidence(self):
        extra, ai = self.confirmed(), self.root / 'ai-responses'
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'no_match_found')
        (self.root / 'outside').mkdir()
        (self.root / 'outside/copy.txt').write_text(text(self.mine), encoding='utf-8')
        (ai / 'linkdir').symlink_to(self.root / 'outside')
        (ai / 'broken.txt').symlink_to(self.root / 'nope')
        (ai / 'sub').mkdir()
        (ai / 'locked.txt').write_text(text(self.mine), encoding='utf-8')
        for name in ('linkdir', 'broken.txt', 'sub', 'locked.txt'):
            with self.subTest(name=name):
                for other in ('linkdir', 'broken.txt', 'sub', 'locked.txt'):
                    if other != name:
                        (ai / other).rename(self.root / f'park-{other}')
                if name in ('sub', 'locked.txt'):
                    os.chmod(ai / name, 0)
                try:
                    _, result = self.run_gate(*extra)
                finally:
                    if name in ('sub', 'locked.txt'):
                        os.chmod(ai / name, 0o700)
                    for parked in self.root.glob('park-*'):
                        parked.rename(ai / parked.name[5:])
                self.assertIsNotNone(result)
                self.assertEqual((result['verdict'], result['comparison_complete']), ('unknown', False))
                self.assertEqual([i['path'].rsplit('/', 1)[1] for i in result['incomplete']], [name])

    def test_broken_default_ai_folder_link_is_not_skipped(self):
        extra = self.confirmed()
        (self.root / 'ai-reference').symlink_to(self.root / 'nope')
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'unknown')

    def test_two_cards_on_one_line_are_refused_and_never_misattributed(self):
        first, second = 'a/back=확인;box:0,0,1,1;upper_right:정상', 'b/back=확인;box:0,0,1,1;upper_left:결함'
        for glue in (' ', '', ';', ', ', '　'):
            with self.subTest(glue=glue):
                self.answer.write_text(first + glue + second + '\n', encoding='utf-8')
                self.assertEqual(self.run_gate(), (2, None))
                unread = []
                found = rater_gate.values(first + glue + second, unread)
                self.assertEqual((unread, [k for k in found if k != 'a/back/upper_right']), ([1], []))


if __name__ == '__main__':
    unittest.main()
