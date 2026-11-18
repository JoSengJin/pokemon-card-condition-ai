"""Generate only memory fixtures for an actual browser; no data discovery or server."""
import base64
import hashlib
import json
from pathlib import Path
import sys
from observation_loop_fixture import fixture
from card_condition.observation_packet import packet_digest
from card_condition.observation_page import render_page


if __name__ == "__main__":
    folder = sys.argv[1]
    dpr = float(sys.argv[2]) if len(sys.argv)>2 else 1
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    controls = Path(__file__).with_name("observation_real_browser_controls.js").read_text()
    for scenario in ("h", "a", "explicit", "viewport", "dpr", "css", "tampered", "missing", "decode", "natural"):
        packet, assets = fixture("A" if scenario == "a" else "H")
        if scenario in ("explicit", "viewport", "dpr", "css"):
            packet["profile"].update(viewport_css=[800,600], device_pixel_ratio=dpr, image_css=[64,64])
            if scenario == "viewport": packet["profile"]["viewport_css"] = [801,600]
            if scenario == "dpr": packet["profile"]["device_pixel_ratio"] = dpr + 1
            packet["packet_id"] = packet_digest(packet)
        page = render_page(packet, assets)
        # Corrupt only the generated synthetic transport, after real Python validation.
        encoded = {ref:base64.b64encode(raw).decode("ascii") for ref,raw in assets.items()}
        if scenario in ("tampered", "decode"):
            encoded["assets/a1.png"] = base64.b64encode(b"not an image").decode("ascii")
        if scenario == "decode":
            packet["entries"][0]["assets"][0]["sha256"] = hashlib.sha256(b"not an image").hexdigest()
        if scenario == "missing": del encoded["assets/a1.png"]
        if scenario == "natural": packet["entries"][0]["assets"][0]["size"] = [9,8]
        if scenario in ("decode", "natural"):
            old = page.split('<script id="packet" type="application/json">')[1].split('</script>')[0]
            packet["packet_id"] = packet_digest(packet)
            page = page.replace(old,json.dumps(packet,ensure_ascii=False))
        old = page.split('<script id="assets" type="application/json">')[1].split('</script>')[0]
        page = page.replace(old,json.dumps(encoded))
        if scenario == "css": page = page.replace('width="64"','width="63"',1)
        page = page.replace('attachResponseControls();initialize();','attachResponseControls();')
        buttons = "".join(f'<button id="{key}">{key}</button>' for key in ("start-test","css-zero","css-restore","ref-change","ref-restore","src-change","src-restore","detach","reattach","proof-test"))
        page = page.replace('</html>','<section id="test-actions">'+buttons+'</section><pre id="environment"></pre><pre id="raw-proof"></pre><script>'+controls+'</script></html>')
        (folder/(scenario+'.html')).write_text(page,encoding="utf-8")
        (folder/(scenario+'.packet.json')).write_text(json.dumps(packet,ensure_ascii=False),encoding="utf-8")
    print(folder)
