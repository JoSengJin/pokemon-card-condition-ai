"use strict";
function zoomGeometryMatches(base,scale,edges,size){
 if(edges[2]-edges[0]!==size[0]||edges[3]-edges[1]!==size[1])return false;
 for(let axis=0;axis<2;axis++){
 let units=[];for(const value of [edges[axis],edges[axis+2],scale]){if(!Number.isFinite(value)||Math.abs(value)>2**128-2**104)return false;if(value===0){units.push(2**-149);continue;}let power=Math.floor(Math.log2(Math.abs(value)));if(Math.abs(value)<2**power)power--;else if(Math.abs(value)>=2**(power+1))power++;units.push(Math.max(2**-149,2**(power-23)));}
 const bound=(units[0]+units[1]+base[axis]*units[2])/2;
 if(Math.abs(size[axis]-base[axis]*scale)>bound)return false;
 }return true;
}
function snapshotZoom(entry){
 const bound=COLLECTION.zoomBindings.get(entry),image=bound.image,rect=image.getBoundingClientRect();
 return {entry_id:entry,ref:bound.asset.ref,asset_sha256:bound.asset.sha256,scale:bound.scale,pan:[...bound.pan],source_size:[image.naturalWidth,image.naturalHeight],
 base_css:bound.base,transformed_css:[rect.width,rect.height],geometry_edges:[rect.left,rect.top,rect.right,rect.bottom],source_matches:!COLLECTION.zoomInvalidated&&image.isConnected&&image.dataset.zoomRef===bound.asset.ref&&image.src===bound.url&&
 (image.currentSrc||image.src)===bound.url&&image.complete&&image.naturalWidth===bound.asset.size[0]&&image.naturalHeight===bound.asset.size[1]&&image.style.transform===bound.transform&&zoomGeometryMatches(bound.base,bound.scale,[rect.left,rect.top,rect.right,rect.bottom],[rect.width,rect.height])};
}
function recordZoom(event,entry){COLLECTION.zoom.push({seq:COLLECTION.zoom.length,event,at:new Date().toISOString(),...snapshotZoom(entry)});}
function invalidateZoom(){COLLECTION.zoomInvalidated=true;COLLECTION.invalidated=true;invalidate({type:"image-zoom"});}
function handleZoom(event){
 if(COLLECTION.zoomObserver?.takeRecords().length){invalidateZoom();return;}
 const entry=event.currentTarget.dataset.entry,bound=COLLECTION.zoomBindings.get(entry),policy=COLLECTION.contract.zoom_policy;
 if(!displayReady()||COLLECTION.zoomInvalidated){invalidateZoom();return;}
 const scale=Number(document.getElementById("zoom-"+entry+"-scale").value),x=Number(document.getElementById("zoom-"+entry+"-x").value),y=Number(document.getElementById("zoom-"+entry+"-y").value);
 let invalid=false;for(const n of [scale,x,y])if(!Number.isFinite(n))invalid=true;for(const n of Object.values(policy))if(n===null)invalid=true;
 if(invalid||scale<policy.scale_min||scale>policy.scale_max||Math.abs(x)>policy.pan_x_limit||Math.abs(y)>policy.pan_y_limit){invalidateZoom();return;}
 bound.scale=scale;bound.pan=[x,y];bound.image.style.transform="translate("+(x*scale)+"px, "+(y*scale)+"px) scale("+scale+")";
 if(COLLECTION.zoomObserver)for(const mutation of COLLECTION.zoomObserver.takeRecords())if(mutation.type!=="attributes"||mutation.target!==bound.image||mutation.attributeName!=="style")invalidateZoom();
 bound.transform=bound.image.style.transform;
 recordZoom("change",entry);
 if(!COLLECTION.zoom.at(-1).source_matches)invalidateZoom();
}
async function attachZoomControls(){
 COLLECTION.zoomBindings=new Map();COLLECTION.zoomInvalidated=false;
 if(COLLECTION.contract.display_profile.observation_mode!=="H"||!displayReady())return;
 try{
 for(const entry of REVIEW.packet.entries){
 let asset;for(const item of entry.assets)if(item.kind==="region")asset=item;const base=COLLECTION.contract.display_profile.image_css||asset.size;
 const original=REVIEW.bindings.get(entry.entry_id+"-region"),image=document.getElementById("zoom-"+entry.entry_id+"-image");
 image.src=original.url;image.style.width=base[0]+"px";image.style.height=base[1]+"px";image.style.transformOrigin="0 0";image.style.transform="translate(0px, 0px) scale(1)";
 await image.decode();
 COLLECTION.zoomBindings.set(entry.entry_id,{image,url:original.url,asset,base,scale:1,pan:[0,0],transform:image.style.transform});recordZoom("initial",entry.entry_id);
 const button=document.getElementById("zoom-"+entry.entry_id+"-apply");let unknown=false;for(const n of Object.values(COLLECTION.contract.zoom_policy))if(n===null)unknown=true;button.disabled=unknown;button.addEventListener("click",handleZoom);
 }
 COLLECTION.zoomObserver=new MutationObserver(invalidateZoom);COLLECTION.zoomObserver.observe(document.getElementById("zoom-root"),{attributes:true,attributeFilter:["src","srcset","data-zoom-ref","style","width","height"],childList:true,subtree:true});
 }catch(error){invalidateZoom();}
}
function finishZoom(){
 if(COLLECTION.zoomObserver?.takeRecords().length)invalidateZoom();
 if(COLLECTION.zoomBindings)for(const entry of COLLECTION.zoomBindings.keys()){recordZoom("export",entry);if(!COLLECTION.zoom.at(-1).source_matches)invalidateZoom();}
}
