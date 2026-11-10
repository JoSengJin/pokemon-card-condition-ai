"""Build five-case offline point-review files from existing frozen evidence only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from review import make_packet,render

if __name__=='__main__':
    source=ROOT/'artifacts/surface-grounding-20261110/packet.json';before=source.read_bytes();packet=make_packet(json.loads(before));out=ROOT/'artifacts/mobile-point-review-20261110';out.mkdir(exist_ok=True)
    with (out/'packet.json').open('x') as f:json.dump(packet,f,ensure_ascii=False)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();pages=[]
    for start in range(0,len(packet['entries']),5):
        indices=list(range(start,min(start+5,len(packet['entries']))));name=f'review-{start//5+1:02d}.html';render(packet,indices,out,name,sha)
        pages.append(dict(file=name,indices=indices,sha256=hashlib.sha256((out/name).read_bytes()).hexdigest(),bytes=(out/name).stat().st_size))
    assert source.read_bytes()==before
    manifest=dict(source_sha=sha,source_packet_id=packet['source_packet_id'],packet_id=packet['packet_id'],canonical_source_unchanged=True,pages=pages,cases=len(packet['entries']),completed=sum(e['completed'] for e in packet['entries']),human_responses_received=0,new_model_calls=0,new_labels=0)
    with (out/'postflight.json').open('x') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(files=len(pages),cases=len(packet['entries']),packet_id=packet['packet_id'],max_bytes=max(p['bytes'] for p in pages)),ensure_ascii=False))
