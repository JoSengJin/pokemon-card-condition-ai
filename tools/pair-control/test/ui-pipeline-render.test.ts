// DOM 저장 대상만 stub. 실제 서버 요약 + 제품 렌더 함수를 사용하며 브라우저 검증과 구분한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pipelineView } from '../src/executor/pipelineView.ts';
import { setup } from './helpers.ts';
import { seed } from './ui-seed.ts';
// @ts-ignore 화면 ESM 모듈
import { renderPipeline } from '../src/ui/js/view-pipeline.js';

for (const scenario of ['current-last', 'current-before-latest', 'empty']) test(`관제 턴 이력: ${scenario}에서 누락·중복 없음`, async () => {
  const e = setup(), el = { innerHTML: '' };
  const original = Object.getOwnPropertyDescriptor(globalThis, 'document');
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { getElementById: () => el } });
  try {
    await seed(e);
    const turns = e.ex.runtime.pipeline!.turns;
    turns.t2.actionResults = [{ id: 'current-result', type: 'note', ok: true, detail: 'CURRENT_UNIQUE_ACTION', at: 'now' }];
    if (scenario === 'current-before-latest') turns.t3 = { ...turns.t1, id: 't3', status: 'failed', actionResults: [{ id: 'latest-result', type: 'note', ok: false, detail: 'LATEST_UNIQUE_ACTION', at: 'now' }] };
    if (scenario === 'empty') e.ex.runtime.pipeline!.turns = {};
    const view = pipelineView(e.ex);
    renderPipeline(view);
    if (scenario === 'empty') {
      assert.equal(view.currentTurn, null);
      assert.match(el.innerHTML, /모델 턴 없음/);
      assert.doesNotMatch(el.innerHTML, /현재 턴|이전 턴/);
    } else {
      assert.equal(view.currentTurn!.id, 't2', '서버가 배열 위치와 무관하게 진행 중인 턴을 선택');
      assert.equal(el.innerHTML.split('CURRENT_UNIQUE_ACTION').length - 1, 1, '현재 턴을 한 번만 표시');
      assert.equal(el.innerHTML.split('자기 확인(독립 검토 아님)').length - 1, 1, '기존 완료 턴 유지');
      if (scenario === 'current-before-latest') assert.equal(el.innerHTML.split('LATEST_UNIQUE_ACTION').length - 1, 1, '최신 실패 턴도 한 번 표시');
    }
  } finally {
    if (original) Object.defineProperty(globalThis, 'document', original);
    else Reflect.deleteProperty(globalThis, 'document');
    e.cleanup();
  }
});
