// 구조 점검: 파싱 → 선언·타입 색인 → 호출 그래프 → 깊이 계산. 각 단계는 앞 단계가 만든 자료만 읽는다.
// 익명·표준 API 콜백도 실제 전이를 계산한다. 타이머·이벤트 등록 콜백은 독립 진입점이다.
// 호출 순환은 별도 보고하며 --check 실패다. 재귀 탐색이나 임의 깊이 절단을 사용하지 않는다.
import path from 'node:path';
import { option, listFiles, parseFiles } from './trace-files.mjs';
import { indexFunctions, indexModules } from './trace-index.mjs';
import { indexTypes } from './trace-types.mjs';
import { indexBindings, indexPromiseFactories } from './trace-bindings.mjs';
import { indexReturnTypes } from './trace-scope-types.mjs';
import { indexSchemas } from './trace-schema.mjs';
import { indexMembers, constructorBindings } from './trace-members.mjs';
import { indexReturns } from './trace-returns.mjs';
import { indexScopes } from './trace-scope.mjs';
import { collectGraph, settleCallbacks } from './trace-graph.mjs';
import { applyManual } from './trace-manual.mjs';
import { computeDepths } from './trace-depth.mjs';
import { resultOf } from './trace-output.mjs';

const args = process.argv.slice(2), root = path.resolve(option(args, 'root') || path.resolve(import.meta.dirname, '..'));
const ctx = { root, files: listFiles(root, option(args, 'files')), parsed: {}, fns: [], classes: {}, exportsOf: {}, importsOf: {}, dataFields: {}, byFile: {}, top: {}, inner: new Map(), methods: {}, exported: {}, definedNames: new Set(), scopes: new Map(), returns: new Map(), graph: new Map(), callbacks: new Map(), externalParams: new Map(), unresolved: [], external: [], depths: new Map(), cycles: [], manual: [], modules: [] };
parseFiles(ctx);
indexFunctions(ctx); indexModules(ctx); indexTypes(ctx); indexBindings(ctx); indexPromiseFactories(ctx); indexReturnTypes(ctx);
indexSchemas(ctx);
indexReturns(ctx);
for (const file of ctx.files) ctx.modules.push({ file, name: '<module>', node: { body: ctx.parsed[file].ast, params: [] }, owner: null, cls: null });
indexScopes(ctx);
indexMembers(ctx); constructorBindings(ctx);
collectGraph(ctx); settleCallbacks(ctx); applyManual(ctx); computeDepths(ctx);
const result = resultOf(ctx, option(args, 'start'));
console.log(JSON.stringify(result, null, 2));
if (args.includes('--check') && (result.overFiles?.length || result.overStarts?.length || result.cycles.length)) process.exit(1);
