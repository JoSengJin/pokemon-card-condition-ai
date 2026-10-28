// 새 메인이 돌려준 응답의 구조 검증. 인수(메인·세대 변경) 전에 응답 전체와 행동 목록·각 항목을 검사한다.
// 반환값은 문제 설명(없으면 null)이며 예외를 던지지 않는다. 알려진 행동 종류의 허용 여부는 승인 장부가 따로 판단한다.
import { ACTION_TYPES } from './mainTypes.ts';

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const optStr = (v: unknown) => v === undefined || typeof v === 'string';

function badAction(a: unknown, i: number): string | null {
  if (!isObj(a)) return `행동[${i}]이 객체가 아님`;
  if (typeof a.id !== 'string' || !a.id.trim()) return `행동[${i}].id가 비어 있거나 문자열이 아님`;
  if (typeof a.type !== 'string' || !(ACTION_TYPES as readonly string[]).includes(a.type)) return `행동[${i}].type을 지원하지 않음: ${String(a.type)}`;
  if (!optStr(a.taskId) || !optStr(a.sha) || !optStr(a.target)) return `행동[${i}]의 taskId·sha·target은 문자열이어야 함`;
  if (a.input !== undefined && !isObj(a.input)) return `행동[${i}].input이 객체가 아님`;
  if (!optStr(a.diffHash) || !optStr(a.note)) return `행동[${i}]의 diffHash·note는 문자열이어야 함`;
  if (a.reviewedFiles !== undefined && (!Array.isArray(a.reviewedFiles) || a.reviewedFiles.some((f) => typeof f !== 'string'))) return `행동[${i}].reviewedFiles가 문자열 배열이 아님`;
  return null;
}

export function badResponse(r: unknown): string | null {
  if (!isObj(r)) return '응답이 객체가 아님';
  if (typeof r.session_id !== 'string' || typeof r.token !== 'string' || typeof r.checkpoint_hash !== 'string' || !Number.isInteger(r.generation)) return 'session_id·generation·token·checkpoint_hash 형식이 틀림';
  const heads = isObj(r.observed) ? r.observed.heads : undefined;
  if (!isObj(heads) || Object.values(heads).some((h) => typeof h !== 'string')) return 'observed.heads가 {작업: SHA 문자열} 객체가 아님';
  if (r.actions === undefined) return null;
  if (!Array.isArray(r.actions)) return 'actions가 배열이 아님';
  for (const [i, a] of r.actions.entries()) { // 같은 ID의 중복은 응답 거부가 아니라 두 번째부터 무시한다(applyActions)
    const why = badAction(a, i);
    if (why) return why;
  }
  return null;
}
