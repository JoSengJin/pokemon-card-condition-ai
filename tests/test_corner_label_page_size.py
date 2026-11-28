"""Corner screen v2: pages split by photo size (max_mb), so small photos share a page and big ones get fewer per page (2026-11-29). Synthetic photos only."""
import json
import random
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools import mobile_corner_label_pages_v2 as v2


class PageSizeTest(unittest.TestCase):
    def test_split_keeps_order_and_limits(self):
        self.assertEqual(v2.split([3, 3, 3, 9, 1], max_bytes=6), [[0, 1], [2], [3], [4]])  # 9 > 6 still gets its own piece
        self.assertEqual(v2.split([1, 1, 1, 1, 1], per_page=2, max_bytes=100), [[0, 1], [2, 3], [4]])
        self.assertEqual(v2.split([5, 5, 5]), [[0, 1, 2]])
        self.assertEqual(v2.split([]), [])

    def test_small_photos_share_a_page_and_a_big_one_stands_alone(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, rng = Path(temp), random.Random(3)
            rows = []
            for name, size in (('s1', (300, 400)), ('s2', (300, 400)), ('big', (1500, 2000)), ('s3', (300, 400))):
                noise = Image.frombytes('RGB', size, bytes(rng.getrandbits(8) for _ in range(size[0] * size[1] * 3)))  # noise: JPEG size grows with pixels
                noise.save(folder / f'{name}.png')
                rows.append(dict(id=name, title='t', side_annotations=dict(back=dict(image=str(folder / f'{name}.png'), box=[.1, .1, .9, .9]))))
            (folder / 'rows.jsonl').write_text('\n'.join(map(json.dumps, rows)), encoding='utf-8')
            sizes = [len(v2.photo(r['side_annotations']['back']['image'], [.1, .1, .9, .9])[0]) for r in rows]
            cap = (sizes[0] + sizes[1]) * 1.05 / 1e6
            self.assertLess(cap * 1e6, sizes[2])  # the big photo alone is over the cap
            pages = v2.main(folder / 'rows.jsonl', 's1 s2 big s3', folder / 'p.html', 'back', max_mb=cap)
            shown = [sorted(json.loads(Path(f'{p}.criteria.json').read_text(encoding='utf-8'))['items']) for p in pages]
            self.assertEqual(shown, [['s1/back', 's2/back'], ['big/back'], ['s3/back']])
            for page in pages:
                photos = re.findall(r'base64,([^"]*)"', page.read_text(encoding='utf-8'))
                self.assertTrue(len(photos) == 1 or sum(map(len, photos)) <= cap * 1e6)


if __name__ == '__main__':
    unittest.main()
