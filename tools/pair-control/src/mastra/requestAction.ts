import { UserError } from '../executor/errors.ts';

/** 요청 인자 해석과 서비스 실행을 같은 호출 층에서 순서대로 수행한다. */
export function act(fn: (...args: any[]) => unknown, input?: unknown) {
  return async (context: any) => {
    try {
      const args = typeof input === 'function' ? await input(context) : [input === undefined ? context : input];
      return context.json({ ok: true, data: await fn(...args) });
    } catch (error) {
      const user = error instanceof UserError;
      return context.json({ ok: false, error: user ? error.message : '내부 오류: ' + (error as Error).message }, user ? 400 : 500);
    }
  };
}
