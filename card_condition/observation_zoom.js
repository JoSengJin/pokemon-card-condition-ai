"use strict";
function snapshotZoom(entry){
 const bound=COLLECTION.zoomBindings.get(entry),image=bound.image,rect=image.getBoundingClientRect();
 const transform="translate("+(bound.pan[0]*bound.scale)+"px, "+(bound.pan[1]*bound.scale)+"px) scale("+bound.scale+")";
 return {entry_id:entry,ref:bound.asset.ref,asset_sha256:bound.asset.sha256,scale:bound.scale,pan:[...bound.pan],source_size:[image.naturalWidth,image.naturalHeight],
 base_css:bound.base,transformed_css:[rect.width,rect.height],source_matches:!COLLECTION.zoomInvalidated&&image.isConnected&&image.dataset.zoomRef===bound.asset.ref&&image.src===bound.url&&
 (image.currentSrc||image.src)===bound.url&&image.complete&&image.naturalWidth===bound.asset.size[0]&&image.naturalHeight===bound.asset.size[1]&&image.style.transform===transform&&rect.width===bound.base[0]*bound.scale&&rect.height===bound.base[1]*bound.scale};
}
function recordZoom(event,entry){COLLECTION.zoom.push({seq:COLLECTION.zoom.length,event,at:new Date().toISOString(),...snapshotZoom(entry)});}
function invalidateZoom(){COLLECTION.zoomInvalidated=true;COLLECTION.invalidated=true;invalidate({type:"image-zoom"});}
function handleZoom(event){
 if(COLLECTION.zoomObserver?.takeRecords().length){invalidateZoom();return;}
 const entry=event.currentTarget.dataset.entry,bound=COLLECTION.zoomBindings.get(entry),policy=COLLECTION.contract.zoom_policy;
 if(!displayReady()||COLLECTION.zoomInvalidated){invalidateZoom();return;}
 const scale=Number(document.getElementById("zoom-"+entry+"-scale").value),x=Number(document.getElementById("zoom-"+entry+"-x").value),y=Number(document.getElementById("zoom-"+entry+"-y").value);
 if([scale,x,y].some(n=>!Number.isFinite(n))||Object.values(policy).some(n=>n===null)||scale<policy.scale_min||scale>policy.scale_max||Math.abs(x)>policy.pan_x_limit||Math.abs(y)>policy.pan_y_limit){invalidateZoom();return;}
 bound.scale=scale;bound.pan=[x,y];bound.image.style.transform="translate("+(x*scale)+"px, "+(y*scale)+"px) scale("+scale+")";
 if(COLLECTION.zoomObserver)for(const mutation of COLLECTION.zoomObserver.takeRecords())if(mutation.type!=="attributes"||mutation.target!==bound.image||mutation.attributeName!=="style")invalidateZoom();
 recordZoom("change",entry);
 if(!COLLECTION.zoom.at(-1).source_matches)invalidateZoom();
}
async function attachZoomControls(){
 COLLECTION.zoomBindings=new Map();COLLECTION.zoomInvalidated=false;
 if(COLLECTION.contract.display_profile.observation_mode!=="H"||!displayReady())return;
 try{
 for(const entry of REVIEW.packet.entries){
 const asset=entry.assets.find(item=>item.kind==="region"),base=COLLECTION.contract.display_profile.image_css||asset.size;
 const original=REVIEW.bindings.get(entry.entry_id+"-region"),image=document.getElementById("zoom-"+entry.entry_id+"-image");
 image.src=original.url;image.style.width=base[0]+"px";image.style.height=base[1]+"px";image.style.transformOrigin="0 0";image.style.transform="translate(0px, 0px) scale(1)";
 await image.decode();
 COLLECTION.zoomBindings.set(entry.entry_id,{image,url:original.url,asset,base,scale:1,pan:[0,0]});recordZoom("initial",entry.entry_id);
 const button=document.getElementById("zoom-"+entry.entry_id+"-apply");button.disabled=Object.values(COLLECTION.contract.zoom_policy).some(n=>n===null);button.addEventListener("click",handleZoom);
 }
 COLLECTION.zoomObserver=new MutationObserver(invalidateZoom);COLLECTION.zoomObserver.observe(document.getElementById("zoom-root"),{attributes:true,attributeFilter:["src","srcset","data-zoom-ref","style","width","height"],childList:true,subtree:true});
 }catch(error){invalidateZoom();}
}
function finishZoom(){
 if(COLLECTION.zoomObserver?.takeRecords().length)invalidateZoom();
 if(COLLECTION.zoomBindings)for(const entry of COLLECTION.zoomBindings.keys()){recordZoom("export",entry);if(!COLLECTION.zoom.at(-1).source_matches)invalidateZoom();}
}
