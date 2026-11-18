"""V2 sidecar checks; callers validate the unchanged v1 base separately."""
from datetime import datetime
import math
from .observation_packet import exact_keys,COLLECTION_STATUS
from .observation_collection_contract import validate_collection_contract
from .observation_zoom import validate_zoom_log

CANDIDATE_KEYS={"schema_version","kind","contract_id","packet_id","data_origin","collection_status","human_truth","eligible_for_collection","base_response","viewport_events","zoom_events","claimed_actor"}


def validate_viewport_events(profile,events):
    if not isinstance(events,list):raise ValueError("viewport events must be a list")
    verified=True;previous=None
    for seq,event in enumerate(events):
        exact_keys(event,{"seq","event","at","layout","visual","dpr","orientation","visibility"},"viewport event")
        if type(event["seq"]) is not int or event["seq"]!=seq or event["event"] not in ("ready","resize","scroll","visibilitychange","export"):raise ValueError("invalid viewport sequence")
        if not isinstance(event["at"],str):raise ValueError("invalid viewport clock")
        at=datetime.fromisoformat(event["at"].replace("Z","+00:00"))
        if at.utcoffset() is None or previous is not None and at<previous:raise ValueError("invalid viewport clock")
        previous=at;size=event["layout"]
        if not isinstance(size,list) or len(size)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) or n<0 for n in size):raise ValueError("invalid layout viewport")
        if any(n==0 for n in size):verified=False
        if profile["viewport_css"] is not None and size!=profile["viewport_css"]:verified=False
        dpr=event["dpr"]
        if dpr is not None and (type(dpr) not in (int,float) or not math.isfinite(dpr) or dpr<=0):raise ValueError("invalid observed DPR")
        if profile["device_pixel_ratio"] is not None and dpr!=profile["device_pixel_ratio"]:verified=False
        if event["orientation"] is not None and not isinstance(event["orientation"],str):raise ValueError("invalid orientation")
        if event["visibility"] not in ("visible","hidden","unknown"):raise ValueError("invalid visibility")
        visual=event["visual"]
        if visual is not None:
            exact_keys(visual,{"width","height","offset_left","offset_top","scale"},"visual viewport")
            for key,value in visual.items():
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError("invalid visual viewport")
                if key in ("width","height","scale") and value<=0:verified=False
            if not profile["zoom_allowed"] and visual["scale"]!=1:verified=False
    return bool(verified and events and events[0]["event"]=="ready" and events[-1]["event"]=="export")


def validate_collection_response(packet,contract,body):
    validate_collection_contract(contract)
    exact_keys(body,CANDIDATE_KEYS,"candidate response")
    if (type(body["schema_version"]) is not int or body["schema_version"]!=2 or body["kind"]!="synthetic_collection_response" or
        body["contract_id"]!=contract["contract_id"] or body["packet_id"]!=packet["packet_id"] or contract["packet_id"]!=packet["packet_id"] or
        contract["display_profile"]!=packet["profile"] or body["data_origin"]!="synthetic_fixture" or body["collection_status"]!=COLLECTION_STATUS or
        body["human_truth"] is not False or body["eligible_for_collection"] is not False or body["claimed_actor"] not in ("human","ai","unknown")):
        raise ValueError("invalid candidate contract/guard")
    viewport=validate_viewport_events(contract["display_profile"],body["viewport_events"])
    zoom=validate_zoom_log(contract,body["zoom_events"],packet)
    return bool(viewport and zoom)
