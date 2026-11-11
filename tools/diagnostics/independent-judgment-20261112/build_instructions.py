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
