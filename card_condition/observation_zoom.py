"""Independent validation of synthetic image zoom observations."""
from datetime import datetime
import math
from .observation_packet import exact_keys

ZOOM_KEYS={"seq","event","at","entry_id","ref","asset_sha256","scale","pan","source_size","base_css","transformed_css","geometry_edges","source_matches"}


def geometry_matches(base,scale,edges,size):
    if edges[2]-edges[0]!=size[0] or edges[3]-edges[1]!=size[1]:return False
    for axis in (0,1):
        units=[]
        for value in (edges[axis],edges[axis+2],scale):
            if not math.isfinite(value) or abs(value)>2**128-2**104:return False
            units.append(2**-149 if value==0 else max(2**-149,2.0**(math.frexp(abs(value))[1]-24)))
        bound=(units[0]+units[1]+base[axis]*units[2])/2
        if abs(size[axis]-base[axis]*scale)>bound:return False
    return True


def validate_zoom_log(contract,events,packet):
    if not isinstance(events,list):raise ValueError("zoom events must be a list")
    if contract["display_profile"]["observation_mode"]=="A":
        if events:raise ValueError("A must not contain image zoom")
        return True
    expected={e["entry_id"]:next(a for a in e["assets"] if a["kind"]=="region") for e in packet["entries"]}
    policy=contract["zoom_policy"];verified=all(v is not None for v in policy.values())
    states={};last_time=None
    for seq,event in enumerate(events):
        exact_keys(event,ZOOM_KEYS,"zoom event")
        if type(event["seq"]) is not int or event["seq"]!=seq or event["event"] not in ("initial","change","export"):raise ValueError("invalid zoom sequence")
        entry=event["entry_id"]
        if not isinstance(entry,str) or entry not in expected:raise ValueError("unknown zoom entry")
        asset=expected[entry]
        if event["ref"]!=asset["ref"] or event["asset_sha256"]!=asset["sha256"]:raise ValueError("zoom asset mismatch")
        if not isinstance(event["at"],str):raise ValueError("invalid zoom time")
        at=datetime.fromisoformat(event["at"].replace("Z","+00:00"))
        if at.utcoffset() is None or last_time is not None and at<last_time:raise ValueError("invalid zoom clock")
        last_time=at
        if type(event["source_matches"]) is not bool:raise ValueError("invalid zoom binding flag")
        for key in ("pan","source_size","base_css","transformed_css","geometry_edges"):
            values=event[key]
            if not isinstance(values,list) or len(values)!=(4 if key=="geometry_edges" else 2) or any(type(n) not in (int,float) or not math.isfinite(n) or key not in ("pan","geometry_edges") and n<=0 for n in values):raise ValueError("invalid zoom dimensions")
        scale=event["scale"]
        if type(scale) not in (int,float) or not math.isfinite(scale) or scale<=0:raise ValueError("invalid zoom scale")
        if event["event"]=="initial":
            if entry in states:raise ValueError("duplicate zoom initial")
            if scale!=1 or event["pan"]!=[0,0]:verified=False
        elif entry not in states:raise ValueError("zoom observation without initial")
        if event["event"]=="export" and (scale,event["pan"])!=states[entry][:2]:verified=False
        states[entry]=(scale,event["pan"],event["event"])
        if not event["source_matches"] or event["source_size"]!=asset["size"]:verified=False
        base=contract["display_profile"]["image_css"] or asset["size"]
        if event["base_css"]!=base or not geometry_matches(base,scale,event["geometry_edges"],event["transformed_css"]):verified=False
        if all(v is not None for v in policy.values()):
            if not policy["scale_min"]<=scale<=policy["scale_max"] or abs(event["pan"][0])>policy["pan_x_limit"] or abs(event["pan"][1])>policy["pan_y_limit"]:verified=False
    return bool(verified and set(states)==set(expected) and all(state[2]=="export" for state in states.values()))
