"""답 가져오기 (계약 C). python -m tools.self_agreement.import_round PLAN ROUND_DIR STATEMENT|- OUT ANSWER...

순서: 원본 보존(OUT/raw/<sha256>.txt) -> 검사 -> round<k>.json 기록. 문장(STATEMENT)이 없거나 `-`이거나 plan의 judge_statement와
다르면, 시각 줄이 없거나 시간대가 없으면 원본만 남기고 종료 코드 2(주체 미확인, round<k>.json 없음). 같은 원본으로 다시 가져올 수 있다.
두 회차는 합치지 않는다. 사람 라벨 파일·정답 형식은 쓰지 않는다.
"""
import json
import sys
from pathlib import Path

from tools import label_criteria as lc
from tools.self_agreement import answers
from tools.self_agreement import plan as cfg


def confirmed(path, plan):
    """주체 확인 문장 파일이 plan의 judge_statement와 글자 단위로 같은지(앞뒤 공백만 무시). 문장을 돌려준다."""
    if path is None or path == '-':
        raise ValueError('주체 확인 문장이 없음(원본만 보존, 주체 미확인)')
    text = Path(path).read_text(encoding='utf-8').strip()
    if text != plan['judge_statement'].strip():
        raise ValueError('주체 확인 문장이 plan의 judge_statement와 다름(원본만 보존, 주체 미확인)')
    return text


def collect(folder, key, raws, out):
    """답 글 전부를 key.json과 대조해 ({n 문자열: 값}, {page_id: 제출시각})을 돌려준다. 쪽마다 기준·크롭 기록(label_criteria.check)도 대조한다."""
    pages = {p['page_id']: p for p in key['pages']}
    values, submitted = {}, {}
    for data in raws:
        pid, stamp, rows = answers.parse(data.decode('utf-8'))
        if pid not in pages:
            raise ValueError(f'이 회차 화면의 글이 아님(화면={pid})')
        if pid in submitted:
            raise ValueError(f'같은 쪽을 두 번 넣음(화면={pid})')
        page = pages[pid]
        if set(rows) != set(page['zones']):
            raise ValueError(f'번호가 화면과 다름: 빠짐 {sorted(set(page["zones"]) - set(rows))}, 모름 {sorted(set(rows) - set(page["zones"]))}')
        proof = lc.check(Path(folder) / (page['file'] + '.criteria.json'), rows, Path(out) / f'unused-{pid}.jsonl')
        for z, n in page['zones'].items():
            if proof[z]['criteria_sha256'] != key['criteria_sha256'] or proof[z]['crop_sha256'] != key['crops'][str(n)]:
                raise ValueError(f'기준·크롭 기록이 key.json과 다름({page["file"]} {z})')
            values[str(n)] = rows[z]
        submitted[pid] = stamp
    if lost := sorted(set(pages) - set(submitted)):
        raise ValueError(f'넣지 않은 쪽이 있음: {lost}')
    return values, submitted


def main(argv):
    try:
        if len(argv) < 5:
            raise ValueError('사용법: PLAN ROUND_DIR STATEMENT|- OUT ANSWER...')
        plan_path, folder, statement, out, *files = argv
        raws = [Path(f).read_bytes() for f in files]
        (Path(out) / 'raw').mkdir(parents=True, exist_ok=True)
        hashes = [answers.keep_raw(Path(out) / 'raw', data) for data in raws]  # 검사보다 먼저
        plan, plan_sha = cfg.load(plan_path)
        key = json.loads((Path(folder) / 'key.json').read_text(encoding='utf-8'))
        if key['plan_sha256'] != plan_sha:
            raise ValueError('key.json의 plan_sha256이 plan.json과 다름')
        text = confirmed(statement, plan)
        values, submitted = collect(folder, key, raws, out)
        record = dict(plan_sha256=plan_sha, selection_sha256=key['selection_sha256'], round=key['round'], judge_confirmed=True, statement=text,
                      submitted=submitted, criteria_sha256=key['criteria_sha256'], screen_sha256=key['screen_sha256'], crops=key['crops'],
                      answers=values, raw=sorted(hashes))
        cfg.write_new(Path(out) / f'round{key["round"]}.json', record)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print('거절:', error, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
