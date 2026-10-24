"""Collect all listing photos, automatically screen eligibility, then export unlabelled pairs."""
import argparse
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from card_condition.ebay_dataset import collect, export_selected, reserve_screen_call, screen_item, select_photos, verify_backs, back_is_complete, decoded_hash, human_back_checks, non_single_listing
from card_condition.review import atomic_write


def review_html(catalog, screens, output, pending_boundary=0):
    panels = []
    for item in catalog['items']:
        screen = screens.get(item['id'], {})
        selection = screen.get('selection', {'status': 'not_screened'})
        verifier = selection.get('back_boundary_verified_by', '')
        photos = []
        for index, photo in enumerate(item['photos']):
            with Image.open(photo['path']) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((420, 520))
                stream = io.BytesIO()
                image.save(stream, 'JPEG', quality=85)
            chosen = '앞면 선택' if selection.get('front') == index else '뒷면 선택' if selection.get('back') == index else ''
            reason = next((p.get('reason', '') for p in screen.get('evidence', {}).get('photos', [])
                           if p.get('index') == index), '')
            photos.append(f'<figure class="{"chosen" if chosen else ""}"><figcaption>사진 {index+1} · {chosen}</figcaption>'
                          f'<a href="{html.escape(Path(photo["path"]).as_uri(), quote=True)}"><img alt="사진 {index+1}" '
                          f'src="data:image/jpeg;base64,{base64.b64encode(stream.getvalue()).decode()}"></a>'
                          f'<p>{html.escape(reason)}</p></figure>')
        panels.append(f'<section><h2>{html.escape(item["title"])}</h2><p>{html.escape(item["id"])} · '
                      f'{html.escape(selection["status"])} · {html.escape(selection.get("reason", ""))}</p>'
                      f'<p>뒷면 경계 확인 출처: {html.escape(verifier) if verifier else "미확인"} · 상태 정답 자동 생성 없음</p>'
                      f'<div class="photos">{"".join(photos)}</div></section>')
    accepted = sum(s.get('selection', {}).get('status') == 'accepted' for s in screens.values())
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>eBay 자동 사진 선별</title><style>body{font:16px/1.5 system-ui;background:#f3f5f9;color:#172537;margin:24px}'
            'section{background:white;padding:20px;border-radius:12px;margin:20px 0}.photos{display:flex;flex-wrap:wrap;gap:12px}'
            'figure{margin:0;padding:12px;width:280px;border:2px solid #ddd}figure.chosen{border-color:#148050}'
            'img{width:100%;max-height:390px;object-fit:contain}figcaption{font-weight:bold}</style>'
            f'<h1>eBay 자동 사진 선별 · {accepted}/{len(catalog["items"])}매물 채택</h1>'
            f'<p>뒷면 추가검증 대기: {pending_boundary}매물. 대기 자료는 학습 폴더로 내보내지 않습니다.</p>'
            '<p>매물의 전체 사진에서 카드 한 장인 앞면과 로고·네 변·모서리가 온전히 보이는 뒷면을 선별합니다. '
            '초록 테두리가 선택된 사진입니다. 비전 모델 선별은 오판할 수 있으며 동일 실물·카드 영역은 라벨링 때 확인합니다. '
            '정상·결함 학습 정답은 자동 생성하지 않았습니다. 이 페이지는 사진 수집 결과이며 AI 상태 분석 성능 평가가 아닙니다.</p>'
            + ''.join(panels) + '</html>')
    Path(output).write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consumer-root', required=True, type=Path)
    parser.add_argument('--learn', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--quota-db', type=Path, help='Required only for explicitly enabled Gemini screening')
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--screen-limit', type=int, help='Explicit screening mode with this attempt cap; omit to collect photos only')
    parser.add_argument('--query', action='append')
    parser.add_argument('--reference-learn', action='append', type=Path, default=[], help='Read-only previous photo roots for duplicate checks')
    parser.add_argument('--confirm-back', action='append', default=[], help='Explicitly human-confirmed eligible back candidate id; repeat as needed')
    parser.add_argument('--reject-back', action='append', default=[], help='Explicitly human-rejected back candidate id; repeat as needed')
    parser.add_argument('--confirmed-by', default='', help='Required reviewer for human back decisions; never a defect label')
    args = parser.parse_args()
    screening_requested = args.screen_limit is not None or bool(args.confirm_back or args.reject_back)
    if args.screen_limit is None:
        args.screen_limit = 0
    if not 0 <= args.screen_limit <= 30:
        parser.error('--screen-limit must be 0–30')
    sys.path.insert(0, str(args.consumer_root.resolve()))
    from pokecollector.providers import EbayProvider, GeminiProvider, request_json
    if args.screen_limit and args.quota_db is None:
        parser.error('--quota-db is required when Gemini screening is explicitly enabled')
    provider = EbayProvider()
    if not provider.configured:
        raise ValueError('Existing eBay API credentials are not configured')
    output = args.output.resolve()
    catalog_path = output / 'catalog.json'
    queries = args.query or ['pokemon card vintage NM', 'pokemon card vintage played', 'pokemon card old back']
    if not catalog_path.exists() or not json.loads(catalog_path.read_text()).get('collection_complete', False):
        collect(provider, request_json, output, args.learn, queries, args.limit, reference_learn=args.reference_learn)
    catalog = json.loads(catalog_path.read_text())
    if Path(catalog['learn']).resolve() != args.learn.resolve():
        raise ValueError('Existing run targets another learn directory')
    if not screening_requested:
        review_html(catalog, {}, output / 'index.html')
        summary = dict(mode='collection_only', candidates=len(catalog['items']),
                       photos=sum(len(item['photos']) for item in catalog['items']),
                       screened=0, accepted=0, gemini_attempts_this_run=0,
                       manifest=None, html=str(output/'index.html'),
                       condition_labels_created=0, model_accuracy_change=None)
        atomic_write(output / 'collection-summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
        print(json.dumps(summary, ensure_ascii=False))
        return
    gemini = GeminiProvider()
    screen_dir = output / 'screening'
    screen_dir.mkdir(exist_ok=True)
    screens, calls = {}, 0
    guard_calls = 0
    def guard(bucket):
        nonlocal guard_calls
        if guard_calls >= args.screen_limit:
            return False
        allowed = reserve_screen_call(args.quota_db, bucket)
        guard_calls += int(allowed)
        return allowed
    gemini.call_guard = guard
    for item in catalog['items']:
        if non_single_listing(item.get('title', '')):
            screens[item['id']] = dict(selection=dict(status='needs_review', reason='제목에 명시된 묶음·선택형 매물 제외'), evidence={})
            continue
        cached = screen_dir / (item['id'] + '.json')
        if cached.exists():
            screen = json.loads(cached.read_text())
            if screen['input_sha256'] != [p['sha256'] for p in item['photos']]:
                raise ValueError('Cached screening does not match photos')
            if any(decoded_hash(Path(p['path']).read_bytes())[0] != p['sha256'] for p in item['photos']):
                raise ValueError('Cached screening photo was modified')
            screen['selection'] = select_photos(item, screen['evidence'], screen['model'])
            atomic_write(cached, json.dumps(screen, ensure_ascii=False, indent=2))
            screens[item['id']] = screen
            continue
        if not gemini.configured or guard_calls >= args.screen_limit:
            break
        try:
            screens[item['id']] = screen_item(item, gemini)
            calls += 1
            atomic_write(cached, json.dumps(screens[item['id']], ensure_ascii=False, indent=2))
            print(json.dumps({'item': item['id'], 'status': screens[item['id']]['selection']['status']}, ensure_ascii=False), flush=True)
        except Exception as exc:
            # Stop at quota/service errors; resuming reuses completed screens instead of spending twice.
            atomic_write(output / 'last-error.json', json.dumps({'item': item['id'], 'error': str(exc)[:300]}, ensure_ascii=False))
            print('Screening stopped; see last-error.json', flush=True)
            break
    chosen = [item for item in catalog['items'] if screens.get(item['id'], {}).get('selection', {}).get('status') == 'accepted']
    human_path = output/'human-back-checks.json'
    human = human_back_checks(chosen, screens, json.loads(human_path.read_text()) if human_path.exists() else {},
                              args.confirm_back, args.reject_back, args.confirmed_by)
    if args.confirm_back or args.reject_back:
        atomic_write(human_path, json.dumps(human, ensure_ascii=False, indent=2))
    unresolved = [item for item in chosen if item['id'] not in human['checks']]
    verified = None
    verify_path = output/'verified-backs.json'
    signature = {item['id']: item['photos'][screens[item['id']]['selection']['back']]['sha256'] for item in unresolved}
    if unresolved and verify_path.exists():
        candidate = json.loads(verify_path.read_text())
        if (candidate.get('prompt_version') == 'ebay-back-boundary-v3'
                and all(candidate['input_sha256'].get(key) == value for key, value in signature.items())):
            verified = candidate
    if unresolved and verified is None and gemini.configured and guard_calls < args.screen_limit:
        try:
            verified = verify_backs(unresolved, screens, gemini)
            atomic_write(verify_path, json.dumps(verified, ensure_ascii=False, indent=2))
        except Exception as exc:
            atomic_write(output/'last-error.json', json.dumps({'stage': 'back_verification', 'error': str(exc)[:300]}, ensure_ascii=False))
    pending_boundary = 0
    for item in chosen:
        check = human['checks'].get(item['id'])
        if check is None and verified:
            check = next((r for r in verified['evidence'] if r['id'] == item['id']), None)
        pending_boundary += int(check is None)
        if check is None or not back_is_complete(check):
            screens[item['id']]['selection'] = dict(status='needs_review', reason=check.get('reason', '') if check else '뒷면 네 변 추가검증 대기')
        else:
            screens[item['id']]['selection']['back_boundary_verified_by'] = ('human: ' + check['reviewed_by']
                if check.get('verification_method') == 'human' else verified['model'])
            screens[item['id']]['selection']['back_boundary_checks'] = check
    selections = {key: value['selection'] for key, value in screens.items()}
    error_path = output/'last-error.json'
    if chosen and pending_boundary == 0 and error_path.exists():
        if json.loads(error_path.read_text()).get('stage') == 'back_verification':
            error_path.unlink()
    accepted = sum(s.get('status') == 'accepted' for s in selections.values())
    if accepted:
        revision = __import__('hashlib').sha256(json.dumps(selections, sort_keys=True).encode()).hexdigest()[:12]
        manifest = output / f'selected-{revision}.jsonl'
        if not manifest.exists():
            export_selected(catalog, selections, manifest)
    else:
        manifest = None
    review_html(catalog, screens, output / 'index.html', pending_boundary)
    summary = dict(candidates=len(catalog['items']), screened=len(screens), accepted=accepted,
                   gemini_attempts_this_run=guard_calls, completed_screenings_this_run=calls,
                   manifest=str(manifest) if manifest else None, html=str(output/'index.html'),
                   condition_labels_created=0, model_accuracy_change=None)
    summary.update(first_stage_accepted=len(chosen), awaiting_boundary_verification=pending_boundary,
                   boundary_verified=bool(chosen) and pending_boundary == 0,
                   human_back_decisions=sum(item['id'] in human['checks'] for item in chosen))
    atomic_write(output / 'summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
