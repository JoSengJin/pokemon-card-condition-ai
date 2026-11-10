"""Synthetic receipt trust-boundary checks; no real photos or human answers created."""
import copy
import json
from pathlib import Path
import tempfile
from manual import SCOPE,validate_manual,ingest_manual,load_reviewed
from review import digest


def rejects(fn,*args):
    try:fn(*args)
    except ValueError:return
    raise AssertionError('Invalid/conflicting input accepted')


if __name__=='__main__':
    packet=dict(schema_version=1,kind='surface_point_review_packet',region_labels_read_only=True,entries=[dict(id='fixture/'+str(i),completed=False,row=dict(image_sha256=str(i)*64,target=0)) for i in range(3)])
    packet['packet_id']=digest(packet)
    rows=[dict(id=e['id'],image_sha256=e['row']['image_sha256'],region_target=0,judgment=j,point=None,location_description='  원문\n보존  ') for e,j in zip(packet['entries'],('defect','unknown',None))]
    answers=dict(schema_version=1,kind='surface_point_review_manual_draft',scope=SCOPE,packet_id=packet['packet_id'],responses=rows)
    validate_manual(packet,answers)
    legacy=copy.deepcopy(answers);del legacy['scope'];rejects(validate_manual,packet,legacy);validate_manual(packet,legacy,SCOPE)
    for field,value in [('id','other'),('region_target',True),('image_sha256','other'),('judgment','unseen'),('point',dict(x=.5,y=.5)),('location_description',None)]:
        bad=copy.deepcopy(answers);bad['responses'][0][field]=value;rejects(validate_manual,packet,bad)
    bad=copy.deepcopy(answers);bad['responses'].append(rows[0]);rejects(validate_manual,packet,bad)
    for field,value in [('scope','model_candidate'),('packet_id','other'),('schema_version',True)]:
        bad=copy.deepcopy(answers);bad[field]=value;rejects(validate_manual,packet,bad)
    done=copy.deepcopy(packet);done['entries'][0]['completed']=True;done['packet_id']=digest(done);bad=copy.deepcopy(answers);bad['packet_id']=done['packet_id'];rejects(validate_manual,done,bad)
    with tempfile.TemporaryDirectory() as temp:
        out=Path(temp);pp=out/'packet.json';aa=out/'answers.json';ledger=out/'ledger';pp.write_text(json.dumps(packet));raw=json.dumps(legacy,ensure_ascii=False,indent=2)+'\r\n';aa.write_bytes(raw.encode())
        target=ingest_manual(pp,aa,ledger,SCOPE);saved=target.read_bytes();receipt=json.loads(saved)
        assert receipt['source_text'].encode()==aa.read_bytes() and receipt['human_point_labels']==[] and receipt['model_candidate_confirmed_ids']==[] and not receipt['training_applied'] and not receipt['existing_region_labels_changed']
        assert receipt['conflicts_with_existing_region']==['fixture/0'] and receipt['human_observations'][0]['location_description']==rows[0]['location_description']
        assert set(load_reviewed(packet,ledger))=={'fixture/0','fixture/1'}
        assert ingest_manual(pp,aa,ledger,SCOPE)==target and target.read_bytes()==saved
        conflict=copy.deepcopy(answers);conflict['responses'][0]['judgment']='normal';aa.write_text(json.dumps(conflict));rejects(ingest_manual,pp,aa,ledger);assert target.read_bytes()==saved and len(list(ledger.glob('*.json')))==1
        receipt['human_observations'][0]['judgment']='normal';target.write_text(json.dumps(receipt));rejects(load_reviewed,packet,ledger)
        assert json.loads(pp.read_text())==packet
    print('PASS: explicit scope/legacy gate;immutable raw bytes incl CRLF;ID/SHA/region/completed guards;unknown reviewed/pending not reviewed;idempotence;conflicts rejected without writes;tamper detected;no exact points/candidate truth/training')
