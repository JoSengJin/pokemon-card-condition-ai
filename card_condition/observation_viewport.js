"use strict";
const COLLECTION={contract:null,viewport:[],zoom:[],invalidated:false};
function readViewport(){
 const visual=window.visualViewport;
 return {layout:[window.innerWidth,window.innerHeight],visual:visual?{width:visual.width,height:visual.height,offset_left:visual.offsetLeft,offset_top:visual.offsetTop,scale:visual.scale}:null,
 dpr:window.devicePixelRatio??null,orientation:window.screen?.orientation?.type??null,visibility:document.visibilityState||"unknown"};
}
function matchesViewport(required,measured){
 if(measured.layout.some(n=>!Number.isFinite(n)||n<=0)||measured.dpr!==null&&(!Number.isFinite(measured.dpr)||measured.dpr<=0))return false;
 if(required.viewport_css!==null&&(required.viewport_css[0]!==measured.layout[0]||required.viewport_css[1]!==measured.layout[1]))return false;
 if(required.device_pixel_ratio!==null&&required.device_pixel_ratio!==measured.dpr)return false;
 if(measured.visual&&([measured.visual.width,measured.visual.height,measured.visual.scale].some(n=>!Number.isFinite(n)||n<=0)||
 [measured.visual.offset_left,measured.visual.offset_top].some(n=>!Number.isFinite(n))))return false;
 return true;
}
function observeViewport(event){
 const measured=readViewport();
 COLLECTION.viewport.push({seq:COLLECTION.viewport.length,event:event.type,at:new Date().toISOString(),...measured});
 if(!matchesViewport(COLLECTION.contract.display_profile,measured)){COLLECTION.invalidated=true;invalidate(event);}
}
function attachViewport(){
 COLLECTION.contract=JSON.parse(document.getElementById("collection-contract").textContent);
 observeViewport({type:"ready"});
 window.addEventListener("resize",observeViewport);window.addEventListener("scroll",observeViewport);
 document.addEventListener("visibilitychange",observeViewport);
 if(window.visualViewport){window.visualViewport.addEventListener("resize",observeViewport);window.visualViewport.addEventListener("scroll",observeViewport);}
 document.getElementById("collection-export").addEventListener("click",exportCollection);
}
