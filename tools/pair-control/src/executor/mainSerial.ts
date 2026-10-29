// 메인 상태를 바꾸는 작업(행동 수행·교대 시작)을 한 줄로 세운다. 같은 실행기에서는 앞 작업이 끝나야 다음 작업이 시작된다.
// 프로세스 안에서만 유효한 순서 보장이며(전역 잠금 아님), 앞 작업이 실패해도 뒤 작업은 이어진다.
// 콜백을 넘기지 않는 방식이다: 호출한 쪽이 try/finally에서 풀기 함수를 부른다(콜백 경유로 호출 전이가 늘지 않게).
const tails = new WeakMap<object, Promise<void>>();

/** 앞선 작업이 끝날 때까지 기다린 뒤 "풀기" 함수를 돌려준다. 반드시 finally에서 호출해야 뒤 작업이 이어진다. */
export async function lock(owner: object): Promise<() => void> {
  const prev = tails.get(owner) ?? Promise.resolve();
  let release!: () => void;
  tails.set(owner, new Promise<void>((resolve) => { release = resolve; }));
  await prev;
  return release;
}
