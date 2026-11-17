"""Synthetic output only. Never discovers photos, labels, caches, or a provider."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from collection_runtime_fixture import candidate_fixture
from card_condition.observation_collection_contract import contract_digest
from card_condition.observation_packet import packet_digest
from card_condition.observation_page import render_page

if __name__=="__main__":
    root=Path(sys.argv[1]);pages=root/"pages";pages.mkdir(parents=True,exist_ok=True)
    for name in ("h","a","unknown","viewport","tampered","missing","decode"):
        packet,assets,contract,_,_,_=candidate_fixture("A" if name=="a" else "H")
        packet["profile"]["image_css"]=[64,64]
        if name=="viewport":packet["profile"]["viewport_css"]=[391,844]
        packet["packet_id"]=packet_digest(packet)
        contract["display_profile"]=copy.deepcopy(packet["profile"]);contract["packet_id"]=packet["packet_id"]
        contract["spec_sha256"]=hashlib.sha256(Path("docs/collaboration/contracts/collection-runtime-v2-20261117.md").read_bytes()).hexdigest()
        if name=="unknown":contract["zoom_policy"]={key:None for key in contract["zoom_policy"]}
        contract["contract_id"]=contract_digest(contract)
        page=render_page(packet,assets,collection_contract=contract)
        # Failure cases corrupt only already-generated synthetic transport.
        encoded={key:base64.b64encode(value).decode("ascii") for key,value in assets.items()}
        if name in ("tampered","decode"):encoded["assets/a1.png"]=base64.b64encode(b"synthetic bad image").decode("ascii")
        if name=="missing":del encoded["assets/a1.png"]
        if name=="decode":
            old_packet=re.search(r'<script id="packet" type="application/json">([\s\S]*?)</script>',page).group(1)
            old_contract=re.search(r'<script id="collection-contract" type="application/json">([\s\S]*?)</script>',page).group(1)
            packet["entries"][0]["assets"][0]["sha256"]=hashlib.sha256(b"synthetic bad image").hexdigest();packet["packet_id"]=packet_digest(packet)
            contract["packet_id"]=packet["packet_id"];contract["contract_id"]=contract_digest(contract)
            page=page.replace(old_packet,json.dumps(packet,ensure_ascii=False)).replace(old_contract,json.dumps(contract,ensure_ascii=True))
        old_encoded=re.search(r'<script id="assets" type="application/json">([\s\S]*?)</script>',page).group(1)
        page=page.replace(old_encoded,json.dumps(encoded))
        page=page.replace('attachResponseControls();initialize().then(attachZoomControls);','attachResponseControls();')
        proof_script="""async function candidateProof(){const raw=document.getElementById('collection-out').value;const bytes=new TextEncoder().encode(raw);const hash=new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));let sha='';for(const n of hash)sha+=n.toString(16).padStart(2,'0');const full=navigator.userAgentData?await navigator.userAgentData.getHighEntropyValues(['fullVersionList']):null;document.getElementById('candidate-proof').textContent=JSON.stringify({bytes:bytes.length,sha256:sha,environment:{ua:navigator.userAgent,full,viewport:[innerWidth,innerHeight],dpr:devicePixelRatio}});}"""
        controls='<button id="start-fixture" onclick="initialize().then(attachZoomControls)">합성 표시 검사 시작</button><button id="css-roundtrip" onclick="const i=document.getElementById(\'zoom-r1-image\');const old=i.style.width;i.style.width=\'1px\';i.style.width=old;">합성 렌즈 CSS 오류 후 복원</button><button id="candidate-proof-button" onclick="candidateProof()">합성 원문 SHA 확인</button><pre id="candidate-proof"></pre>'
        page=page.replace('</html>',controls+'<script>'+proof_script+'</script></html>')
        (pages/(name+'.html')).write_text(page,encoding='utf-8')
        (pages/(name+'.packet.json')).write_text(json.dumps(packet),encoding='utf-8')
        (pages/(name+'.contract.json')).write_text(json.dumps(contract),encoding='utf-8')
    print(pages)
