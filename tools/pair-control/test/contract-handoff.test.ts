import { startPrompt } from '../src/executor/executorPrompt.ts';
// 메인이 쓴 계약으로 구현 에이전트가 이어 개발하게 하는 흐름: 요청문·답 나누기, 읽을 문서, 시작 프롬프트, 모호한 계약 경고.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderContract } from '../src/executor/contractFile.ts';
import { planTask } from '../src/executor/prepare.ts';
// @ts-ignore 화면용 ESM 모듈(타입 없음)
import { buildMainRequest, parseContractReply } from '../src/ui/js/contract-request.js';
import { setup, task } from './helpers.ts';

const REPLY = `## 목표
순위 감독 초기화 대조 실험의 worker 구현

## 완료 조건
- 단위 테스트 통과
1. 보고서만 추가하지 않음

## 허용 파일
- \`card_condition/a.py\` (신규)
- tests/test_a.py
- 설명만 있는 줄

## 읽을 문서
- \`README.md\`

## 상세 지시
1단계: 구현. 문서로 끝내지 말 것.
- 단계마다 커밋`;

test('요청문: 메인이 누구든 구현자·점유 작업·답변 형식·커밋된 문서 규칙을 담는다', () => {
  for (const main of ['codex', 'claude']) {
    const t = buildMainRequest({ main, agent: main === 'codex' ? 'claude' : 'codex', active: [{ taskId: 'task-1', agent: 'claude', allowedFiles: ['card_condition/x.py'] }], hint: '표면 오류 감소' });
    assert.match(t, new RegExp('메인\\(' + (main === 'codex' ? 'Codex' : 'Claude') + '\\)'));
    assert.match(t, /data·artifacts·\.backups가 없고, 커밋된 파일만/);
    assert.match(t, /task-1 \(claude\): card_condition\/x\.py/);
    assert.match(t, /## 목표[\s\S]*## 완료 조건[\s\S]*## 허용 파일[\s\S]*## 읽을 문서[\s\S]*## 상세 지시/);
    assert.match(t, /문서·보고서로 끝내지 말고/);
    assert.match(t, /표면 오류 감소/);
    assert.match(t, /\[관찰 가능한 목표 하나\./, '메인이 준 일반형 양식이 들어감');
    assert.match(t, /side-evidence-validator-batch-20261025/, '과거 사례 예시가 들어감');
    assert.match(t, /찾지 못함"이라고 적고 추정하지 않습니다/);
  }
  assert.match(buildMainRequest({}), /- \(없음\)/);
});

test('답 나누기: 절별로 칸을 나누고 경로가 아닌 항목은 제외·없는 절은 알린다', () => {
  const r = parseContractReply(REPLY);
  assert.equal(r.goal, '순위 감독 초기화 대조 실험의 worker 구현');
  assert.deepEqual(r.doneCriteria, ['단위 테스트 통과', '보고서만 추가하지 않음']);
  assert.deepEqual(r.allowedFiles, ['card_condition/a.py', 'tests/test_a.py']);
  assert.deepEqual(r.readDocs, ['README.md']);
  assert.deepEqual(r.rejected, ['설명만 있는 줄']);
  assert.match(r.prompt, /문서로 끝내지 말 것/);
  assert.deepEqual(r.missing, []);
  const none = parseContractReply('그냥 알아서 해줘');
  assert.equal(none.missing.length, 4);
  assert.deepEqual(parseContractReply('## 목표\nx').missing, ['완료 조건', '허용 파일', '상세 지시']);
  // 양식의 빈칸을 채우지 않고 돌려준 경우: 자리표시자는 경로로 읽지 않는다. 허용 파일 절의 금지·무시 줄은 상세 지시로 간다.
  const tpl = parseContractReply('## 목표\n[목표]\n\n## 완료 조건\n- [조건]\n\n## 허용 파일\n- [정확한 기존 파일 경로]\n- `a/b.py`\n금지: 데이터·라벨\n무시 산출물: artifacts/x/\n\n## 읽을 문서\n- AGENTS.md\n\n## 상세 지시\n- 구현');
  assert.deepEqual(tpl.allowedFiles, ['a/b.py']);
  assert.deepEqual(tpl.readDocs, ['AGENTS.md']);
  assert.ok(tpl.rejected.includes('[정확한 기존 파일 경로]'));
  // 설명 문장의 첫 단어는 경로가 아니다(예: "side-evidence 계약 초안과 직접 관련 보고서"). 백틱 경로·괄호 주석은 그대로 허용한다.
  const desc = parseContractReply('## 읽을 문서\n- `AGENTS.md`\n- PAIR_CODING.md\n- docs/a.md (신규)\n- side-evidence 계약 초안과 직접 관련 보고서\n- 허용 파일의 호출 코드와 테스트\n- develop\n- `card_condition/x.py` 설명');
  assert.deepEqual(desc.readDocs, ['AGENTS.md', 'PAIR_CODING.md', 'docs/a.md', 'card_condition/x.py']);
  assert.deepEqual(desc.rejected, ['side-evidence 계약 초안과 직접 관련 보고서', '허용 파일의 호출 코드와 테스트', 'develop']);
  assert.match(tpl.prompt, /- 구현[\s\S]*허용 파일 절의 부가 지시:\n금지: 데이터·라벨\n무시 산출물: artifacts\/x\//);
});

test('계약 파일: 읽을 문서는 있을 때만 절과 read_docs를 넣어 기존 계약(해시)을 바꾸지 않는다', async () => {
  const env = setup();
  try {
    const base = { ...task(env, 'task-a'), prompt: '', doneCriteria: [], conflictGroups: [], requiredModules: [], postChecks: [], env: 'none' } as any;
    const without = renderContract({ ...base, readDocs: [] });
    assert.ok(!without.includes('읽을 문서') && !without.includes('read_docs'));
    assert.equal(without, renderContract(base), 'readDocs가 없는 기존 입력도 같은 결과');
    const withDocs = renderContract({ ...base, readDocs: ['README.md'] });
    assert.match(withDocs, /## 읽을 문서\n\n- `README.md`\n\n## allowed_files/);
    assert.match(withDocs, /"read_docs": \[\s*"README.md"\s*\]/);
  } finally { env.cleanup(); }
});

test('미리보기: 완료 조건·읽을 문서가 모두 없으면 경고, 없는 문서는 준비 불가, 있으면 통과', async () => {
  const env = setup();
  try {
    const vague = await planTask(env.ex, { agent: 'claude', mode: 'manual', goal: '성능 개선', allowedFiles: ['src_b/'] });
    assert.ok(vague.warnings.some((w) => /보고서만 쓰고 끝날 수 있음/.test(w)));
    const broad = await planTask(env.ex, { agent: 'claude', mode: 'manual', goal: '성능 개선' });
    assert.ok(broad.warnings.some((w) => /기본 범위\(폴더 전체\)/.test(w)));
    assert.ok(!vague.warnings.some((w) => /기본 범위\(폴더 전체\)/.test(w)), '허용 파일을 직접 적으면 경고하지 않음');
    const mock = await planTask(env.ex, { agent: 'claude', mode: 'mock', goal: '연습', allowedFiles: ['src_b/'] });
    assert.ok(!mock.warnings.some((w) => /보고서만 쓰고/.test(w)), 'mock은 경고하지 않음');
    const missing = await planTask(env.ex, { agent: 'claude', mode: 'manual', goal: 'x', allowedFiles: ['src_b/'], readDocs: ['docs/없는문서.md'] });
    assert.equal(missing.ok, false);
    assert.ok(missing.checks.some((c) => !c.ok && /기준 커밋에 없는 문서: docs\/없는문서\.md/.test(c.detail)));
    const ok = await planTask(env.ex, { agent: 'claude', mode: 'manual', goal: 'x', allowedFiles: ['src_b/'], readDocs: ['README.md'], doneCriteria: ['끝'] });
    assert.ok(ok.ok, JSON.stringify(ok.checks));
    assert.deepEqual(ok.task!.readDocs, ['README.md']);
    assert.ok(!ok.warnings.some((w) => /보고서만 쓰고/.test(w)));
  } finally { env.cleanup(); }
});

test('시작 프롬프트: 읽을 문서를 자동 실행·수동 모두에 넣고, 보고서만 쓰고 끝내지 말라는 규칙과 근거 없을 때의 종료 규칙을 담는다', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a', { mode: 'manual', readDocs: ['README.md'] }));
    const p = await startPrompt(env.ex, 'task-a');
    assert.deepEqual(p.extraDocs, ['README.md']);
    assert.match(p.text, /README\.md/);
    assert.match(p.text, /문서 검토·상태 보고서만으로 끝내지 마세요/);
    assert.match(p.text, /data·artifacts가 없습니다/);
    assert.match(p.text, /필요한 계약 보완을 한 줄로 보고한 뒤 종료/);
    assert.match(p.text, /git add \.`로 전체를 올리지 마세요/);
    assert.match(p.text, /untracked 파일을 빈 작업물로 보고 삭제·초기화하지 마세요/);
    await env.ex.assign(task(env, 'task-b', { mode: 'manual', allowedFiles: ['src_b/'], readDocs: ['없는문서.md'] }));
    await assert.rejects(startPrompt(env.ex, 'task-b'), /시작 HEAD에 없는 문서/);
  } finally { env.cleanup(); }
});

test('시작 프롬프트 구조: 메인이 쓰던 8절 형식(식별·확인·목표·소유권·제한·검증·진행·인계)과 조건부 항목', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a', { mode: 'manual', doneCriteria: ['결과 파일 추가'] }));
    const p = (await startPrompt(env.ex, 'task-a', { unattended: true })).text;
    const heads = [...p.matchAll(/^## (\d)\. (.+)$/gm)].map((m) => m[1] + m[2]);
    assert.deepEqual(heads, ['1작업 식별', '2먼저 확인할 것', '3목표와 완료 조건', '4파일 소유권', '5구현·실행 제한', '6검증', '7진행 방식', '8산출물·커밋·최종 인계']);
    assert.match(p, /구현 담당 Claude다\. 메인 담당 Codex가 정한 아래 작업 계약 범위에서만/);
    assert.match(p, /- task_id: task-a\n- task 문서\(계약\): docs\/collaboration\/tasks\/task-a\.md/);
    assert.match(p, /문서와 실제 상태가 다르면 추정해서 진행하지 말고 차이를 보고하세요/);
    assert.match(p, /파일당 함수 정의 최대 7개, 주요 호출 전이 최대 4회/);
    assert.match(p, /합성 테스트 통과를 실제 모델 성능 개선으로 보고하지 마세요/);
    assert.match(p, /task_id \/ branch \/ base_sha, 최종 전체 커밋 SHA와 적용 순서/);
    assert.ok(!p.includes('HTML_REPORTING'), '허용 파일에 docs/collaboration이 없으면 HTML 안내를 넣지 않음');
    assert.ok(!p.includes('./develop'));
    await env.ex.assign(task(env, 'task-b', { mode: 'manual', allowedFiles: ['docs/collaboration/'] }));
    assert.match((await startPrompt(env.ex, 'task-b')).text, /HTML_REPORTING\.md가 요구하면 HTML 경로와 열기·렌더 확인 결과를 구분해 적으세요/);
  } finally { env.cleanup(); }
});

test('./develop 안내: 관제 실행부가 감싸 시작하는 에이전트에게는 중첩 실행을 요구하지 않고, 수동 세션은 기존 안내를 유지한다', async () => {
  const env = setup();
  try {
    const dev = { allowedFiles: ['card_condition/x.py'] };
    await env.ex.assign(task(env, 'task-a', { ...dev, mode: 'manual' }));
    const manual = (await startPrompt(env.ex, 'task-a')).text;
    assert.match(manual, /`\.\/develop -- <수정 명령>` 안에서 수행하세요/);
    await env.ex.assign(task(env, 'task-b', { ...dev, mode: 'real' }));
    const run = (await startPrompt(env.ex, 'task-b')).text;
    assert.match(run, /관제 도구가 worktree의 `\.\/develop` 잠금을 획득한 상태로 시작했습니다\. `\.\/develop`을 직접 실행하지 말고/);
    assert.ok(!run.includes('안에서 수행하세요(AGENTS.md)'), '중첩 실행 요구 문구 없음');
  } finally { env.cleanup(); }
});
