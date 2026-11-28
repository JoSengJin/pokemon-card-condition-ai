"""Human label screens must say what LABELING_PROTOCOL.md (the canonical criteria) says (docs/agent/QUALITY_RULES.md single-source-criteria)."""
import re
import unittest
from pathlib import Path

from card_condition.label_instructions import SURFACE_INSTRUCTIONS

ROOT = Path(__file__).resolve().parents[1]
SURFACE_TOOLS = ('mobile_surface_label_pages', 'mobile_surface_label_pages_v2', 'relabel_consistency_page', 'relabel_zone_pages')
# Each clause must be found in BOTH the canonical text and the screen; different wording on one side = drift.
CLAUSES = {
    '표면': ('긁힘·뜯김·눌림·구김·접힘·얼룩·인쇄외자국', '면위의흰마모자국\\(화이트닝\\)', '옆면테두리(?:의)?백화', '둥근(?:모서리|귀퉁이)끝의마모만',
           '카드밖배경·홀로반사·인쇄무늬', '반사인지(?:손상|실제마모)인지구분이?(?:안되|되지않으)', '판단불가', '미확인', '(?:카드전체가정상|전체카드정상)'),
    '엣지': ('마모·백화·찍힘·들뜸', '둥근(?:귀퉁이끝|부분)만의(?:손상|문제)', '(?:면안쪽|안쪽표면)기스·오염'),
    '모서리': ('뭉개짐·찍힘·백화·접힘', '확대해서보이면크기와관계없이결함', 'mm크기문턱은두지않', '확대해도반사인지(?:실제)?마모인지구분(?:되지않으|안되)면',
            '추정', '(?:직선)?테두리(?:만|\\(엣지\\))의마모·백화', '(?:면안쪽|표면)기스·오염'),
    '관찰 제한': ('빛반사·흐림·가림·잘림·저해상도·심한각도·그림자', '일부에만있어도', '카드상태를일부라도볼수없으면제한', '나머지로(?:카드상태를)?충분히볼수있으면정상',
              '카드뒷면이아니거나\\(금속·복제등\\)네변이사진에다보이지않으면자격아님', '판단이안서면모름'),
    # Phone screens for the same cells: same wording where the sentence is the same; 자격아님·모름 become 미확인 because these screens have no such buttons.
    '관찰 제한(휴대폰)': ('빛반사·흐림·가림·잘림·저해상도·심한각도·그림자', '일부에만있어도', '카드상태를일부라도볼수없으면제한', '나머지로(?:카드상태를)?충분히볼수있으면정상',
                    '카드뒷면이아니거나\\(금속·복제등\\)네변이사진에다보이지않(?:으면|거나)', '추정하지않', '판단이안서면'),
}
CLAUSES['모서리 재판정'] = CLAUSES['모서리']
# 2026-11-28 모서리 v2 (D-1·D-2): only the new screen is held to the v2 sentences. The re-judgment pages keep the v1 clause set (alias split instead of editing them; they are older screens' siblings).
CLAUSES['모서리 v2'] = CLAUSES['모서리'] + ('구분되는흰흔적은크기와관계없이결함', '반사인지실제마모인지구분이안될때만판단불가', '둥근끝과직선엣지에걸쳐있으면걸친두위치모두결함')
ALIAS = {'관찰 제한(휴대폰)': '관찰 제한', '모서리 재판정': '모서리', '모서리 v2': '모서리'}  # which canonical text a screen is held to


V2_PARAGRAPH = ('모서리의 둥근 끝에서 뭉개짐·찍힘·백화·접힘이 사진을 확대하여 명확히 구분되면 크기와 관계없이 결함으로 판정한다. 확대해도 반사인지 실제 마모인지 구분되지 않거나 '
                '가림·흐림 등으로 판별할 수 없으면 판단 불가로 처리하며, 원본 사진에 없는 세부정보는 추정하지 않는다.')  # 2026-11-28 user decision A, verbatim


def plain(text):
    return re.sub(r'<[^>]+>|[\s*`\'"‘’“”]', '', text)


def canonical(cell):
    """The canonical text for one cell: its row plus shared/judgment sections, as listed under '기준 정본'."""
    cell, text = ALIAS.get(cell, cell), (ROOT / 'LABELING_PROTOCOL.md').read_text(encoding='utf-8')
    row = next((line for line in text.splitlines() if line.startswith(f'| {cell}:')), '')
    heading = {'모서리': '후면 모서리 결함 수준', '관찰 제한': '후면 관찰 제한 판정 문구 보완'}.get(cell, '위치로 먼저 구분하기')
    section = re.search(rf'^## {heading}.*?(?=^## |\Z)', text, re.S | re.M).group(0)
    section = '\n'.join(line for line in section.splitlines() if not line.startswith('| '))  # other cells' rows do not count
    shared = re.search(r'^## 정상·결함·불확실을 구분하기.*?(?=^## )', text, re.S | re.M).group(0) if cell == '표면' else ''
    return plain(row + section + shared)


def screen(cell):
    tool = {'엣지': 'mobile_edge_zone_label_pages', '모서리': 'mobile_corner_label_pages', '관찰 제한': 'ebay_back_label_pages',
            '관찰 제한(휴대폰)': 'mobile_visibility_label_pages', '모서리 재판정': 'relabel_corner_blind_pages',
            '모서리 v2': 'mobile_corner_label_pages_v2'}.get(cell)
    return plain((ROOT / f'tools/{tool}.py').read_text(encoding='utf-8') if tool else SURFACE_INSTRUCTIONS)


def drift(cell, canon, shown):
    return [c for c in CLAUSES[cell] if not (re.search(c, canon) and re.search(c, shown))]


class LabelCriteriaSourceTest(unittest.TestCase):
    def test_screens_agree_with_the_canonical_criteria(self):
        for cell in CLAUSES:
            with self.subTest(cell=cell):
                self.assertEqual(drift(cell, canonical(cell), screen(cell)), [])
        self.assertIn('판단이안서면미확인입니다', screen('관찰 제한(휴대폰)'))  # this screen has no 모름 button: 판단 불가 maps to 미확인

    def test_removing_any_clause_from_either_side_is_detected(self):
        for cell, clauses in CLAUSES.items():
            for clause in clauses:
                with self.subTest(cell=cell, clause=clause):
                    self.assertNotIn(clause, drift(cell, canonical(cell), screen(cell)))  # present on both sides first
                    self.assertIn(clause, drift(cell, re.sub(clause, '', canonical(cell)), screen(cell)))
                    self.assertIn(clause, drift(cell, canonical(cell), re.sub(clause, '', screen(cell))))

    def test_canonical_corner_v2_states_d1_d2_and_what_stays_open(self):
        # The canonical side of the v2 sentences; the v2 screen is held to them in the other tests (cell '모서리 v2').
        text = canonical('모서리')
        for clause in (re.escape(plain(V2_PARAGRAPH)), '걸친두위치모두결함', '표면·엣지(?:에대한)?적용범위는미정', '옛기준\\(v1\\)라벨', '소급하지않'):
            with self.subTest(clause=clause):
                self.assertRegex(text, clause)

    def test_v2_screen_does_not_write_what_the_canonical_leaves_undecided(self):
        from tools import mobile_corner_label_pages_v2 as v2
        shown = plain(v2.INSTRUCTIONS)
        for undecided in ('판본', '표면·엣지(?:에대한)?적용', '\\d(?:\\.\\d)?mm', '그림'):  # judgment version V, surface/edge scope, boundary numbers or picture
            with self.subTest(undecided=undecided):
                self.assertNotRegex(shown, undecided)
        self.assertRegex(canonical('모서리'), '표면·엣지(?:에대한)?적용범위는미정')  # still undecided on the canonical side

    def test_surface_screens_use_the_shared_copy_instead_of_their_own(self):
        for name in SURFACE_TOOLS:
            source = (ROOT / f'tools/{name}.py').read_text(encoding='utf-8')
            with self.subTest(tool=name):
                self.assertIn('from card_condition.label_instructions import SURFACE_INSTRUCTIONS', source)
                self.assertIn('+ SURFACE_INSTRUCTIONS +', source)
                self.assertIn(f'tools/{name}.py', (ROOT / 'LABELING_PROTOCOL.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
