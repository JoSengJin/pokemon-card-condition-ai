"""TN 무작위 60곳 후보 확인 묶음(6x10). 기존 후보 화면 재사용. 학습·추론·라벨 변경 0, 응답 수집 전."""
import json
import random
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/diagnostics/mobile-point-review-20261110'))
from review import digest
from ten import render_ten
OUT = ROOT / 'artifacts/tn-hidden-defect-20261111'
N, PER_FILE, SEED = 60, 10, 20261111


def sample():
    grounding = json.load(open(ROOT / 'artifacts/surface-grounding-20261110/packet.json'))['entries']
    seen = {a['id'].split('/point-review/')[0] for a in json.load(open(ROOT / 'artifacts/mobile-candidate-review-complete-20261111/candidate-answers.json'))['responses']}
    pool = [e for e in grounding if e['outcome'] == 'TN' and not e['known_points'] and e['row']['id'] not in seen]
    rng = random.Random(SEED); rng.shuffle(pool); groups, chosen = set(), []
    for e in pool:
        if e['row']['group'] not in groups and len(chosen) < N:
            groups.add(e['row']['group']); chosen.append(e)
    return chosen


def packet(chosen):
    entries = []
    for old in chosen:
        e = dict(old); top = old['evidence']['top_index']
        e.update(id=old['row']['id'] + '/point-review/' + str(top), completed=False, selection_reason='tn_hidden_defect_sample',
                 candidate=dict(state='unreviewed', token=top, box=old['evidence']['top_geometry']['box']))
        entries.append(e)
    p = dict(schema_version=1, kind='surface_point_review_packet', source_packet_id='397ed4fb79b6ff215a6cd4ec5d582b86b8cd1f9af7db63cbe3dc713c820f10cc',
             entries=entries, region_labels_read_only=True, automatic_training=False)
    p['packet_id'] = digest(p); return p


def main():
    OUT.mkdir(exist_ok=True); p = packet(sample()); (OUT / 'packet.json').write_text(json.dumps(p, ensure_ascii=False))
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(); files = []
    for k in range(0, len(p['entries']), PER_FILE):
        name = f'tn-{k // PER_FILE + 1:02d}.html'; files.append(dict(file=name, **render_ten(p, list(range(k, k + PER_FILE)), OUT, name, sha)))
    (OUT / 'manifest.json').write_text(json.dumps(dict(packet_id=p['packet_id'], seed=SEED, files=files, source_sha=sha, human_responses=0), indent=1))
    print(json.dumps(files))


if __name__ == '__main__':
    main()
