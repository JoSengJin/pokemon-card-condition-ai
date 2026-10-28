// 메인 에이전트(누가 메인이든)에게 "구현 에이전트가 이어서 개발할 계약"을 써 달라고 요청하는 프롬프트를 만들고,
// 메인이 준 답을 새 작업 폼 칸으로 나누는 순수 함수들. 규칙 기반이며 LLM을 쓰지 않고 브라우저·서버 없이 테스트한다.
// 수동으로 할 때 "메인에게 프롬프트를 달라고 한다"를 도구 안에서 같은 형식으로 반복할 수 있게 한다.
// 답변 형식·작성 예시는 메인(Codex)이 실제로 Claude용 계약을 쓰던 방식을 설명하며 준 "관제 도구용 계약 작성 요청문 초안"(2026-10-28)이다.

const LABEL = { codex: 'Codex', claude: 'Claude' };

const GENERAL = `## 목표

[관찰 가능한 목표 하나. 어떤 입력을 받아 어떤 산출물/검사 결과를 만들지 쓴다.]

## 완료 조건

- [단계별 기능 완료 조건과 이를 확인할 검사]
- [수치 판정 기준이 있으면 기준 ID·분모·사전 고정값]
- [실패·불명확·사람 의존 시 종료/보류 조건]
- [인계: 전체 SHA, 변경 파일, 실제 검사 결과, 미검증, 위험, 롤백]

## 허용 파일

- [정확한 기존 파일 경로]
- [정확한 신규 파일 경로]
금지: [데이터·라벨·비밀·운영·타 작업 소유 파일]
무시 산출물: [필요한 경우 정확한 산출 경로와 용도]

## 읽을 문서

- AGENTS.md
- PAIR_CODING.md
- [배정 task 및 직접 관련 계약/보고서/코드/테스트]
- [데이터가 없으면 검증 가능한 고정 근거·SHA·합성 fixture 위치]

## 상세 지시

- base_sha: [전체 SHA]
- branch/worktree: [작업 ID 및 격리 경로]
- 계약된 입력·출력·호출자·보존할 기존 동작: [...]
- 변경 변수 하나: [...]
- 구조 기준: 파일별 함수 수와 주요 호출 경로 깊이 [...]
- 검사 명령: [...]
- 실제 데이터·사람 판단·외부 호출 금지/분리 조건: [...]
- 모르는 사실은 추정하지 말고 해당 항목만 보류한다. 독립 단계는 계속한다.
- 단계별 커밋/인계 규칙: [...]
- 메인 통합·실험 권한 경계: [...]`;

const EXAMPLE = `## 목표

side-evidence 초안의 선언된 근거 구조를 선택 실행 검증기와 독립 CLI로 구현하고,
합성 JSON/JSONL 파일의 구조·SHA·참조·경로 대조와 보존 동작을 회귀 테스트한다.
사람 진술의 의미·진실성이나 독립성을 판정하지 않는다.

## 완료 조건

- API \`validate_sidecar(sidecar_path, evidence_root)\`와 독립 모듈 CLI 구현.
- 구조·요약, 파일 SHA·참조·경로, CLI 입출력·오류·기존 출력 보존을 단계별 검사.
- A1–A3/R1–R12를 합성 파일로 검증하고 누락·중복·경로 이탈 반례를 검사.
- 지정 unittest, compileall, \`git diff --check\` 결과와 미실행 검사를 기록.
- 단계별 전체 SHA 순서, 변경 파일, 구조 기준, 위험, 롤백을 handoff에 기록.

## 허용 파일

- \`card_condition/side_evidence.py\` (신규)
- \`card_condition/side_evidence_cli.py\` (신규)
- \`tests/test_side_evidence.py\` (신규)
- \`tests/test_side_evidence_sources.py\` (신규)
- \`tests/test_side_evidence_cli.py\` (신규)
- \`docs/collaboration/tasks/side-evidence-validator-batch-20261025.md\`
- \`docs/collaboration/reports/side-evidence-validator-batch-20261025.md\` (신규)

금지: 기존 공용 CLI·data coverage 코드·설정·데이터·snapshot·라벨·모델·PokeCollector·외부 AI·main 통합·push.

## 읽을 문서

- \`AGENTS.md\`
- \`PAIR_CODING.md\`
- side-evidence 계약 초안과 직접 관련 보고서
- 허용 파일의 호출 코드와 테스트

## 상세 지시

- 작업은 배정 \`base_sha\`와 격리 branch/worktree에서만 수행한다.
- 합성 fixture는 실제 파일 바이트에서 SHA를 계산한다.
- 상대 경로만 root 내부에서 읽고, 절대경로·\`..\`·root 밖 symlink·특수 파일을 거부한다.
- 사람 의미·독립성 판정은 \`semantic_verification: false\`로 명시한다.
- 모르는 정책 결정은 해당 항목만 미해결로 두고 독립 구현 단계는 계속한다.
- 단계별 의미 단위로 커밋하고 전체 \`git add .\`를 하지 않는다.
- 실제 inventory, 사진, 라벨, 학습·추론, 외부 AI 호출, main 통합은 하지 않는다.
- 인계 시 전체 SHA 순서와 실제 검사 결과, 미실행 항목을 기록한다.`;

/** 메인에게 보낼 요청문. active는 지금 파일을 점유 중인 작업들(겹치지 않는 대상을 고르게 하는 근거). */
export function buildMainRequest({ main = 'codex', agent = 'claude', active = [], hint = '' } = {}) {
  const busy = active.length
    ? active.map((t) => '- ' + t.taskId + ' (' + t.agent + '): ' + (t.allowedFiles || []).join(', ')).join('\n')
    : '- (없음)';
  const L = [
    '# 구현 에이전트용 작업 계약 작성 요청',
    '',
    '당신은 메인(' + (LABEL[main] || main) + ')입니다. 기본 checkout에서 data·artifacts·실험 기록을 볼 수 있습니다.',
    '구현은 ' + (LABEL[agent] || agent) + '가 별도 worktree에서 합니다. 그 worktree에는 data·artifacts·.backups가 없고, 커밋된 파일만 볼 수 있습니다.',
    '그래서 구현 에이전트가 근거를 직접 찾게 두지 말고, 현재 배정 작업과 실제 최신 기록(AGENTS.md·PAIR_CODING.md 기준)을 확인해 아래 형식의 계약을 당신이 먼저 정해 주세요.',
    '새 학습·추론·외부 AI 호출·커밋은 이 요청에서 하지 않습니다.',
  ];
  if (hint.trim()) L.push('', '방향 힌트(사용자): ' + hint.trim());
  L.push(
    '',
    '## 지켜 줄 것',
    '- 가설·대상은 하나만 정하고, 이미 실패한 가설은 새 근거 없이 다시 고르지 않습니다. 파일이 달라도 같은 API·실험 자원을 쓰면 겹친 것으로 봅니다.',
    '- data·artifacts에 있던 근거는 커밋된 문서·고정 입력·SHA·수치·합성 fixture로 옮겨 "읽을 문서"에 적습니다. 커밋되지 않은 경로는 구현 에이전트가 볼 수 없습니다.',
    '- 우선순위 문서(CONDITION_ANALYSIS_TODO.md 등)나 근거를 찾지 못하면 "찾지 못함"이라고 적고 추정하지 않습니다. 맡길 구현이 없거나 계약을 확정할 수 없으면 코딩 계약 대신 "읽기 전용 검토" 또는 "맡길 개발 없음"으로 답합니다.',
    '- 상세 지시에 "문서·보고서로 끝내지 말고 코드와 단위 테스트까지 구현하라"를 넣습니다(과거 전달 프롬프트에서 계약을 실제 행동으로 잇는 문구였습니다).',
    '- 보내기 전에 허용 파일이 아래 점유 작업·금지 경로와 겹치지 않는지, 경로가 실제로 존재하는지(새 파일은 "신규" 표시), base_sha가 전체 SHA인지 확인합니다.',
    '',
    '## 지금 파일을 점유 중인 작업',
    busy,
    '',
    '## 답변 형식 (제목과 순서를 그대로 지켜 주세요)',
    GENERAL,
    '',
    '## 작성 예시 (과거 사례: side-evidence-validator-batch-20261025)',
    EXAMPLE,
  );
  return L.join('\n').replace(/\n{3,}/g, '\n\n');
}

const SECTION = { goal: /^목표$/, done: /^완료\s*조건$/, files: /^허용\s*파일$/, docs: /^읽을\s*문서$/, prompt: /^상세\s*지시$/ };

function bullets(text) {
  return text.split('\n').map((l) => l.trim()).filter((l) => /^([-*]|\d+[.)])\s+/.test(l)).map((l) => l.replace(/^([-*]|\d+[.)])\s+/, '').trim()).filter(Boolean);
}

/**
 * 항목에서 경로만 꺼낸다. `a/b.py` 설명 → a/b.py(백틱 경로는 뒤에 설명이 있어도 됨).
 * 백틱이 없으면 항목 전체가 경로 하나(뒤에 괄호 주석만 허용)이고 '/' 또는 '.'을 포함해야 한다.
 * 그렇지 않으면 "side-evidence 계약 초안과 …" 같은 설명 문장의 첫 단어를 경로로 잘못 읽는다. 경로가 아니면 null.
 */
function pathOf(item) {
  const m = item.match(/^`([^`]+)`/) || item.match(/^([A-Za-z0-9_.\/-]+)(?:\s*\([^)]*\))?$/);
  const p = m && m[1].trim();
  if (!p || p.includes(' ') || !/^[A-Za-z0-9_.][A-Za-z0-9_.\/-]*$/.test(p)) return null;
  return m[0].startsWith('`') || /[\/.]/.test(p) ? p : null;
}

/** 메인의 답을 폼 칸으로 나눈다. 찾지 못한 절은 missing에, 경로로 읽지 못한 항목은 rejected에 알린다. */
export function parseContractReply(text) {
  const parts = {};
  let key = null;
  for (const line of String(text || '').split('\n')) {
    const h = line.match(/^#{1,3}\s*(.+?)\s*$/);
    const name = h && Object.keys(SECTION).find((k) => SECTION[k].test(h[1].replace(/[`*]/g, '').trim()));
    if (name) { key = name; parts[key] = []; continue; }
    if (key) parts[key].push(line);
  }
  const body = (k) => (parts[k] || []).join('\n').trim();
  const rejected = [];
  const paths = (k) => bullets(body(k)).map((i) => { const p = pathOf(i); if (!p) rejected.push(i); return p; }).filter(Boolean);
  // 허용 파일 절의 "금지: …"·"무시 산출물: …" 같은 비목록 줄은 경로가 아니라 지시이므로 상세 지시에 덧붙인다.
  const fileNotes = body('files').split('\n').map((l) => l.trim()).filter((l) => l && !/^([-*]|\d+[.)])\s+/.test(l));
  const out = {
    goal: body('goal').split('\n').map((l) => l.trim()).find(Boolean) || '',
    doneCriteria: bullets(body('done')),
    allowedFiles: paths('files'),
    readDocs: paths('docs'),
    prompt: [body('prompt'), fileNotes.length ? '허용 파일 절의 부가 지시:\n' + fileNotes.join('\n') : ''].filter(Boolean).join('\n\n'),
    rejected,
  };
  const empty = { 목표: !out.goal, '완료 조건': !out.doneCriteria.length, '허용 파일': !out.allowedFiles.length, '상세 지시': !out.prompt };
  out.missing = Object.keys(empty).filter((k) => empty[k]);
  return out;
}
