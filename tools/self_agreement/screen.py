"""두 회차가 같은 화면 글을 쓰도록 모으는 곳 (계약 B). 회차 번호·구역 신원은 화면에 넣지 않는다."""
import hashlib
from pathlib import Path

from tools import label_criteria as lc
from tools import relabel_corner_blind_pages as blind
from tools import relabel_zone_pages as zp

JS = Path(__file__).with_name('screen.js').read_text(encoding='utf-8')
STYLE = zp.STYLE  # import 시점 값을 잡아 둔다
GUIDE = ('<p>이전 판정·모델 점수는 보이지 않습니다. 파란 사각형 안 구역만 판정하세요. 확신이 없으면 판단 불가로 두세요. '
         '자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>')
INSTRUCTIONS = blind.INSTRUCTIONS + GUIDE
CRITERIA_SHA = lc.sha(INSTRUCTIONS.encode())
BUTTONS = '<div class="row"><button data-v="정상">정상</button><button data-v="결함">결함</button><button data-v="불가">판단 불가</button></div>'
FOOT = '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'


def screen_sha(crop_name):
    """화면 틀(스타일·버튼·스크립트·크롭 이름)의 해시. 같은 화면이면 두 회차가 같다."""
    return lc.sha('\n'.join([STYLE, BUTTONS, FOOT, JS, crop_name]).encode())


def page_id(round_no, page_no, crop_name, crop_hashes):
    text = '|'.join([str(round_no), str(page_no), CRITERIA_SHA, screen_sha(crop_name), ','.join(crop_hashes)])
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def article(number, jpeg_b64):
    return f'<article data-id="z{number}"><h2>구역 {number}</h2><img alt="" src="data:image/jpeg;base64,{jpeg_b64}">{BUTTONS}</article>'


def page_text(title, pid, body):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><style>{STYLE}</style><h1>{title}</h1>{INSTRUCTIONS}{body}{FOOT}'
            f'<script>const PID="{pid}";\n{JS}</script></html>')
