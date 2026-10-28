// 메인 상태를 바꾸는 작업(행동 수행·교대 시작)을 한 줄로 세운다. 같은 실행기에서는 앞 작업이 끝나야 다음 작업이 시작된다.
// 프로세스 안에서만 유효한 순서 보장이며(전역 잠금 아님), 앞 작업이 실패해도 뒤 작업은 이어진다.
const tails = new WeakMap<object, Promise<unknown>>();

export function serialize<T>(owner: object, fn: () => Promise<T>): Promise<T> {
  const next = (tails.get(owner) ?? Promise.resolve()).then(fn);
  tails.set(owner, next.catch(() => undefined));
  return next;
}
