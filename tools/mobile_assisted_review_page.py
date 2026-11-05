"""Generate a three-zone, script-free assisted review. Keep radios at their question, not offscreen at the top."""
import argparse
import base64
import hashlib
import html
import itertools
import json
from pathlib import Path

STATES = (("normal", "정상"), ("defect", "결함"), ("unsure", "모르겠음"), ("unseen", "미확인"))
HELP = {
    "edge": "구역의 바깥 테두리선 마모·백화·찍힘만 보세요. 면 안쪽의 기스·오염은 제외합니다.",
    "surface": "인쇄면 안쪽의 긁힘·눌림·얼룩·흰 마모 자국을 보세요. 옆면 백화나 둥근 모서리 끝의 마모만 있으면 표면 결함에서 제외합니다.",
    "corner": "구역의 둥근 귀퉁이 끝 뭉개짐·찍힘·백화·접힘만 보세요. 직선 테두리와 면 안쪽의 자국은 제외합니다.",
}
STYLE = """*{box-sizing:border-box}body{margin:0 auto;padding:18px 14px 110px;max-width:680px;font:17px/1.6 system-ui;color:#182e42;background:#f5f7fb}h1{font-size:25px}h2{font-size:21px}header,section{background:white;border:1px solid #d4dce7;border-radius:14px;padding:18px;margin-bottom:18px}p{margin:10px 0}.hint{font-size:14px;color:#475569}.crop{display:block;width:100%;max-width:400px;height:auto;margin:12px auto}.overview{width:100%;height:auto}fieldset{border:0;margin:16px 0 0;padding:0}legend{font-weight:700;margin-bottom:8px}.choices{display:grid;grid-template-columns:1fr 1fr;gap:10px}.choices label{display:flex;align-items:center;gap:8px;min-height:58px;padding:10px;border:2px solid #cbd5e1;border-radius:10px;cursor:pointer}.choices input{position:static;width:22px;height:22px;flex-shrink:0;accent-color:#184f9b}.choices span{flex:1;padding:3px;border-radius:4px}.choices input:checked+span{background:#e4eeff;color:#184f9b;font-weight:700}.choices input:focus-visible{outline:3px solid #e19b00;outline-offset:2px}.result-case{display:none}textarea{width:100%;height:350px;font:14px/1.5 ui-monospace,monospace;padding:10px;border:1px solid #91a4bd;border-radius:8px;color:#182e42;background:white}.dock{position:fixed;bottom:0;left:0;right:0;background:#f5f7fbf5;padding:10px 14px;border-top:1px solid #cad4e1}.dock a{display:block;text-align:center;max-width:652px;margin:auto;background:#184f9b;color:white;border-radius:10px;min-height:54px;padding:14px;text-decoration:none;font-weight:700}summary{cursor:pointer;color:#174f95}#results{scroll-margin-top:12px}"""


def load_review(directory):
    root = Path(directory)
    review = json.loads((root / "review-map.json").read_text())
    if hashlib.sha256((root / "result.json").read_bytes()).hexdigest() != review["result_sha256"]:
        raise ValueError("Review is not tied to the current frozen model result")
    if [item["number"] for item in review["selections"]] != [1, 2, 3]:
        raise ValueError("Exactly three ordered review zones are required")
    for item in review["selections"]:
        if item["part"] not in HELP or item.get("human_label") not in {None, *(v for _, v in STATES)}:
            raise ValueError("Unknown review part or human state")
    images = {str(n): (root / f"zone-{n}.png").read_bytes() for n in (1, 2, 3)}
    images["overview"] = (root / "priority-overview.png").read_bytes()
    return review, images


def page(review, images):
    cards, rules, outputs = [], [], []
    for item in review["selections"]:
        n = item["number"]
        selected = item.get("human_label") or "미확인"
        controls = "".join(
            f'<label><input type="radio" id="c{n}-{key}" name="choice-{n}" value="{value}"'
            + (" checked" if value == selected else "")
            + f'><span>{"선택 안 함" if key == "unseen" else value}</span></label>'
            for key, value in STATES
        )
        encoded = base64.b64encode(images[str(n)]).decode()
        cards.append(
            f'<section data-number="{n}"><h2>{n}. {html.escape(item["label"])}</h2>'
            f'<p>{HELP[item["part"]]}</p><img class="crop" alt="{html.escape(item["label"])} 확대 사진" src="data:image/png;base64,{encoded}">'
            f'<fieldset><legend>{n}번 확인 결과</legend><div class="choices">{controls}</div></fieldset></section>'
        )
    for combination in itertools.product(STATES, repeat=3):
        suffix = "-".join(key for key, _ in combination)
        scope = "form.review" + "".join(f":has(#c{n}-{key}:checked)" for n, (key, _) in enumerate(combination, 1))
        rules.append(f"{scope} #result-{suffix}{{display:block}}{scope} #manual-fallback{{display:none}}")
        values = [value for _, value in combination]
        payload = dict(review_id=review["request_id"], result_sha256=review["result_sha256"],
                       answers={f'{item["number"]}.{item["part"]}.{item["area"]}': value for item, value in zip(review["selections"], values)})
        outputs.append(
            f'<div class="result-case" id="result-{suffix}"><p><b>① {values[0]} / ② {values[1]} / ③ {values[2]}</b></p>'
            '<p>결과 칸을 길게 눌러 모두 선택 → 복사한 뒤 Codex 채팅에 붙여넣어 주세요.</p>'
            f'<textarea readonly spellcheck="false" aria-label="복사할 답">{html.escape(json.dumps(payload, ensure_ascii=False, indent=2))}</textarea></div>'
        )
    manual = dict(review_id=review["request_id"], result_sha256=review["result_sha256"],
                  answers={f'{item["number"]}.{item["part"]}.{item["area"]}': "직접 입력: 정상 / 결함 / 모르겠음 / 미확인" for item in review["selections"]})
    overview = base64.b64encode(images["overview"]).decode()
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>카드 구역 검토 · 선택 결과 복사</title><style>' + STYLE + "\n" + "\n".join(rules) + '</style></head><body>'
        '<header><h1>뒷면 · 3곳 확인</h1><p>각 사진 바로 아래에서 답을 선택하세요. 모두 고른 뒤 <b>선택한 결과로 이동</b>을 누르고 결과 칸을 길게 눌러 <b>모두 선택 → 복사</b>하여 Codex 채팅에 붙여넣어 주세요.</p>'
        '<p class="hint">선택은 자동 저장되지 않습니다. 이미 전달한 답이 있으면 그대로 표시합니다. 안 본 곳은 선택 안 함, 구분하기 어려우면 모르겠음으로 두세요. AI가 고른 구역을 보는 보조 검토이며 독립 평가가 아닙니다.</p>'
        f'<details><summary>전체 사진에서 위치 보기</summary><img class="overview" alt="검토 구역 1, 2, 3의 위치" src="data:image/png;base64,{overview}"></details></header>'
        '<form class="review">' + "".join(cards) + '<section id="results"><h2>복사할 결과</h2>' + "".join(outputs)
        + '<div id="manual-fallback"><p><b>이 미리보기에서는 선택 결과 연결을 지원하지 않습니다.</b> 아래 값을 직접 적거나 채팅에 <code>1=…, 2=…, 3=…</code>로 답해 주세요.</p>'
        + '<textarea aria-label="직접 입력할 답">' + html.escape(json.dumps(manual, ensure_ascii=False, indent=2))
        + '</textarea></div><p class="hint">정상은 해당 구역의 해당 종류에 대한 답이며, 카드 전체 정상이라는 뜻이 아닙니다. 채팅에 붙여넣어야 답이 전달됩니다.</p></section></form>'
        '<div class="dock"><a href="#results">선택한 결과로 이동 · 길게 눌러 복사</a></div></body></html>'
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("Keep prior review HTML as evidence; use a new output name")
    review, images = load_review(args.directory)
    args.output.write_text(page(review, images), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
