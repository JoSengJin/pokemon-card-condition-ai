"use strict";
function exportCollection(){
 observeViewport({type:"export"});
 if(COLLECTION.invalidated)invalidate({type:"candidate-export"});
 exportResponse();
 const contract=COLLECTION.contract;
 const body={schema_version:2,kind:"synthetic_collection_response",contract_id:contract.contract_id,packet_id:contract.packet_id,
 data_origin:"synthetic_fixture",collection_status:"not_executable_pending_collection_contract_approval",human_truth:false,eligible_for_collection:false,
 base_response:JSON.parse(document.getElementById("out").value),viewport_events:COLLECTION.viewport,zoom_events:COLLECTION.zoom,claimed_actor:"unknown"};
 const raw=JSON.stringify(body,null,2);document.getElementById("collection-out").value=raw;return raw;
}
