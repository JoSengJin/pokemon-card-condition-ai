"""Memory-generated candidate bytes and invented actor identities only."""
import copy
from observation_loop_fixture import fixture,response_fixture
from test_observation_collection_contract import contract_fixture
from card_condition.observation_collection_contract import contract_digest


def candidate_fixture(mode="H"):
    packet,assets=fixture(mode);c=contract_fixture(mode)
    c["zoom_policy"].update(scale_min=1,scale_max=2,pan_x_limit=8,pan_y_limit=8);c["assignment_ref"]="fixture-assignment"
    c["contract_id"]=contract_digest(c)
    base=response_fixture(packet);base["observations"]["events"][0]["at"]="2026-11-18T00:00:00Z"
    view=dict(seq=0,event="ready",at="2026-11-18T00:00:00Z",layout=[800,600],visual=None,dpr=1,orientation=None,visibility="visible")
    viewport=[view,dict(view,seq=1,event="export")];zoom=[]
    if mode=="H":
        a=packet["entries"][0]["assets"][1]
        z=dict(seq=0,event="initial",at=view["at"],entry_id="r1",ref=a["ref"],asset_sha256=a["sha256"],scale=1,pan=[0,0],
               source_size=a["size"],base_css=a["size"],transformed_css=a["size"],source_matches=True)
        zoom=[z,dict(z,seq=1,event="export")]
    body=dict(schema_version=2,kind="synthetic_collection_response",contract_id=c["contract_id"],packet_id=packet["packet_id"],data_origin="synthetic_fixture",
              collection_status=packet["collection_status"],human_truth=False,eligible_for_collection=False,base_response=base,viewport_events=viewport,zoom_events=zoom,claimed_actor="human")
    assignment=dict(assignment_id=c["assignment_ref"],contract_id=c["contract_id"],session_id=base["session_id"],rater_id="fixture-rater",observation_mode=mode,evidence_origin="synthetic_fixture")
    context=dict(source_type="synthetic_fixture",assignment_id=c["assignment_ref"],contract_id=c["contract_id"],session_id=base["session_id"],rater_id="fixture-rater",received_at="2026-11-18T00:00:01Z")
    return packet,assets,c,copy.deepcopy(body),context,assignment
