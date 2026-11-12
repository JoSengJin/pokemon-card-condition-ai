"""독립 판정 안내문 새 출력 생성. SURFACE_INSTRUCTIONS 원문 + 문턱 문장 하나. 기존 파일·HTML은 덮어쓰지 않는다(없는 경로에만 쓴다)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from card_condition.label_instructions import SURFACE_INSTRUCTIONS
THRESHOLD = ('<p><b>이 판정의 결함 문턱(하나):</b> 이 화면에 고정된 크기 그대로(확대·축소 없이) 보이는 <b>카드 인쇄면 안쪽 자국은 결함</b>입니다. '
             '위 안내의 “확대해서”는 이 판정에서는 적용하지 않으며, 보이지 않는 미세 자국은 결함으로 치지 않습니다.</p>')
OUT = Path('artifacts/independent-judgment-20261112/instructions.html')
if __name__ == '__main__':
    if OUT.exists(): sys.exit(f'exists: {OUT}')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('<!doctype html><meta charset="utf-8">' + SURFACE_INSTRUCTIONS + THRESHOLD, encoding='utf-8'); print(OUT)

# ---- v2 (amendment_2, 파일럿 1의 정의 모호 지적 3개 보완; 문턱 문장은 불변) ----
CLARIFY = [
    '① 가장자리: 카드 끝선에 붙어 끝선을 따라 이어지는 흰 점·선(백화)은 엣지라서 결함이 아닙니다. 끝선에서 벗어나 인쇄 무늬(파란 테두리 띠 포함) 위로 들어온 긁힘·자국은 인쇄면 안쪽이라서 결함입니다. 끝선에 붙었는지 안쪽인지 구분이 안 되면 판단 불가(other)입니다.',
    '② 반사: 슬리브·케이스·슬랩 때문에 생긴 반사는 밝은 면이나 띠가 사진 각도에 따라 번져 보이는 것이며 결함이 아닙니다. 반사에 가려 인쇄면이 안 보이면 판단 불가(reflection)입니다. 반사 위나 옆에 별도로 선명한 긁힘·자국 모양이 따로 보이면 결함입니다.',
    '③ 작은 점: 이 크기 그대로 한눈에 점·선으로 구분되는 자국만 결함입니다. 확대해야만 겨우 보이는 한두 화소 수준의 점은 결함이 아닙니다. 점인지 인쇄 무늬·압축 잡음인지 구분이 안 되면 판단 불가(not_visible)입니다.',
]
OUT2 = Path('artifacts/independent-judgment-20261112/instructions_v2.html')
if __name__ == '__main__' and not OUT2.exists():
    OUT2.write_text('<!doctype html><meta charset="utf-8">' + SURFACE_INSTRUCTIONS + THRESHOLD + '<p><b>보충 안내:</b></p><ul>' + ''.join(f'<li>{c}</li>' for c in CLARIFY) + '</ul>', encoding='utf-8'); print(OUT2)
