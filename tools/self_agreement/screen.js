// 두 회차 공통 화면 스크립트 (계약 B). 페이지가 앞에 `const PID="..."`를 붙인다. document만 쓰며 버튼마다 리스너는 한 번만 붙인다.
const arts = [...document.querySelectorAll('article')];
function now() { return new Date(Date.now() + 9 * 36e5).toISOString().slice(0, 19) + '+09:00'; }
function build() {
  const lines = ['# 화면=' + PID, '# 제출시각=' + now()];
  for (const a of arts) lines.push(a.dataset.id + '=' + (a.dataset.v || '미확인'));
  return lines.join('\n');
}
function show() { document.getElementById('out').value = build(); }
function pick(a, b) { a.dataset.v = b.dataset.v; for (const x of a.querySelectorAll('button')) x.classList.toggle('on', x === b); }
function copy() {
  const t = document.getElementById('out'), m = document.getElementById('msg');
  show(); t.focus(); t.select();
  try { m.textContent = document.execCommand('copy') ? '복사됨. 채팅에 붙여넣으세요.' : '아래 칸을 길게 눌러 직접 복사하세요.'; } catch (e) { m.textContent = '아래 칸을 길게 눌러 직접 복사하세요.'; }
}
for (const a of arts) for (const b of a.querySelectorAll('button')) b.addEventListener('click', () => { pick(a, b); show(); });
document.getElementById('copy').onclick = copy;
show();
