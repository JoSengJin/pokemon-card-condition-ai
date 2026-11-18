"""Static phone page for the R1 real-device check. Measures what the browser reports and asks the user to confirm 9 scenarios.
The pasted-back text is human/real-device evidence for the main agent to review. It is NOT synthetic evidence and is never auto-fed to r1_status."""
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from card_condition.observation_evidence import R1_SCENARIOS  # noqa: E402

STEPS = {
    'default_display': '아무것도 하지 말고 이 칸의 측정값만 확인',
    'address_bar': '화면을 위아래로 끝까지 스크롤해 주소창이 접히고 펴지게 하세요',
    'rotation': '폰을 가로로 돌렸다가 세로로 되돌리세요',
    'keyboard': '아래 입력칸을 눌러 키보드를 띄웠다가 닫으세요',
    'touch': '아래 큰 버튼을 손가락으로 3번 누르세요',
    'h_zoom_app_log': '사진 확대는 아직 구현 전: 두 손가락으로 이 페이지를 한 번 벌렸다 오므리세요(페이지 확대 기록 확인)',
    'h_zoom_external': '브라우저·OS 확대(크롬 메뉴의 확대, 글자 크기)를 쓸 수 있으면 한 번 바꿔 보고 되돌리세요. 못 하면 불가',
    'a_separation': 'A 화면에서 확대가 막히는지는 실제 화면이 있어야 확인 가능. 지금은 해당 없음 선택',
    'export_receive': '맨 아래 결과 칸을 길게 눌러 전체 복사해 채팅에 붙여넣기. 붙여넣은 글자 수·체크값이 아래 값과 같아야 함',
}
CHOICES = ('미확인', '됨', '안 됨', '해당 없음')
STYLE = ("body{font:16px/1.5 system-ui;margin:12px}article{border:1px solid #888;border-radius:8px;padding:10px;margin:10px 0}"
         "select,input,button,textarea{font-size:18px;min-height:44px}textarea{width:100%;height:240px}pre{white-space:pre-wrap;margin:4px 0;background:#eee;padding:6px}")
SCRIPT = """const M={vmin:1e9,vmax:0,rot:0,kbmin:1e9,touch:0,zmax:1};
const vv=window.visualViewport;
function snap(){M.vmin=Math.min(M.vmin,innerHeight);M.vmax=Math.max(M.vmax,innerHeight);if(vv){M.zmax=Math.max(M.zmax,vv.scale);M.kbmin=Math.min(M.kbmin,vv.height)}}
addEventListener('resize',snap);addEventListener('scroll',snap);if(vv){vv.addEventListener('resize',snap);vv.addEventListener('scroll',snap)}
addEventListener('orientationchange',()=>{M.rot++});matchMedia('(orientation:landscape)').addEventListener('change',()=>{M.rot++;render()});
document.getElementById('tap').addEventListener('click',()=>{M.touch++;render()});
function fnv(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)>>>0}return h.toString(16)}
function auto(){snap();return {default_display:'ua='+navigator.userAgent+' inner='+innerWidth+'x'+innerHeight+' screen='+screen.width+'x'+screen.height+' dpr='+devicePixelRatio+' secure='+isSecureContext,
address_bar:'innerHeight min/max='+M.vmin+'/'+M.vmax,rotation:'orientation_changes='+M.rot,keyboard:'visualViewport_min_h='+(vv?M.kbmin:'null'),
touch:'taps='+M.touch+' touchpoints='+navigator.maxTouchPoints,h_zoom_app_log:'page_scale_max='+(vv?M.zmax:'null'),h_zoom_external:'dpr_now='+devicePixelRatio,a_separation:'-',export_receive:'-'}}
function render(){const a=auto();document.querySelectorAll('[data-m]').forEach(e=>e.textContent=a[e.dataset.m]);
const lines=[...document.querySelectorAll('article')].map(x=>x.dataset.s+'='+x.querySelector('select').value+' | '+a[x.dataset.s]);
const body=lines.join('\\n');document.getElementById('out').value=body+'\\nlen='+body.length+' fnv='+fnv(body);
document.getElementById('sum').textContent='len='+body.length+' fnv='+fnv(body)}
document.querySelectorAll('select').forEach(s=>s.addEventListener('change',render));setInterval(render,1000);render();"""


def article(name):
    options = ''.join(f'<option>{c}</option>' for c in CHOICES)
    return (f'<article data-s="{name}"><h3>{html.escape(name)}</h3><p>{html.escape(STEPS[name])}</p>'
            f'<pre data-m="{name}"></pre><select>{options}</select></article>')


def page():
    guide = ('<h2>R1 실기기 확인</h2><p>폰의 크롬에서 열었다면 그대로, 아니면 열린 화면에서 아래 9칸을 하나씩 하고 선택하세요. '
             '맨 아래 결과를 전체 복사해 채팅에 붙여 주세요. 사진·정답 라벨과 무관한 화면 점검입니다.</p>'
             '<input placeholder="키보드 시험용 입력칸"><br><button id="tap" style="width:100%;height:80px">터치 시험 버튼</button>')
    body = guide + ''.join(article(n) for n in R1_SCENARIOS) + '<p>붙여넣기 대조값: <b id="sum"></b></p><textarea id="out" readonly></textarea>'
    return f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>R1 실기기 확인</title><style>{STYLE}</style>{body}<script>{SCRIPT}</script>'


def main(out_path):
    Path(out_path).write_text(page(), encoding='utf-8')
    return len(R1_SCENARIOS)


if __name__ == '__main__':
    print(main(sys.argv[1]))
