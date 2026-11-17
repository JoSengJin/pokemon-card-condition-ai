"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const {makeHarness}=require("./observation_browser_fixture.cjs");
function lensBox(){const scale=Number(this.style.transform.match(/scale\(([^)]+)\)/)[1]);return {width:this.badWidth||4*scale,height:4*scale};}
async function main(){
 const page=fs.readFileSync(process.argv[2],"utf8"),h=makeHarness(page);
 const contract=page.match(/<script id="collection-contract" type="application\/json">([^]*?)<\/script>/)[1];
 for(const id of ["collection-contract","collection-out","collection-export","zoom-root","zoom-r1-apply","zoom-r1-scale","zoom-r1-x","zoom-r1-y"])
 h.doc.elements.set(id,{textContent:id==="collection-contract"?contract:"",value:id.endsWith("scale")?"1":"0",dataset:{entry:"r1"},listeners:new Map(),addEventListener(type,fn){this.listeners.set(type,fn);}});
 const lens={...h.doc.images[1],id:"zoom-r1-image",dataset:{zoomRef:"assets/a2.png"},style:{},getBoundingClientRect:lensBox};h.doc.elements.set(lens.id,lens);
 for(const id of ["viewport-code","zoom-code","collection-response-code"])vm.runInContext(page.match(new RegExp('<script id="'+id+'">([^]*?)<\\/script>'))[1],h.context);
 h.context.attachResponseControls();h.context.attachViewport();await h.context.initialize();await h.context.attachZoomControls();
 h.doc.getElementById("zoom-r1-scale").value="2";h.doc.getElementById("zoom-r1-x").value="1";
 h.context.handleZoom({currentTarget:h.doc.getElementById("zoom-r1-apply")});h.context.exportCollection();
 const body=JSON.parse(h.doc.getElementById("collection-out").value);
 assert.equal(body.zoom_events.at(-1).scale,2);assert.deepEqual(body.zoom_events.at(-1).pan,[1,0]);assert.equal(body.zoom_events.at(-1).source_matches,true);
 assert.equal(h.context.displayReady(),true);assert.equal(h.doc.images[1].width,4);
 lens.badWidth=1;h.context.finishZoom();assert.equal(h.context.displayReady(),false,"lens CSS mismatch must lock browser");
 h.doc.notes[0].value="  preserved\n ";lens.src="changed";h.context.finishZoom();lens.src=h.doc.images[1].src;
 assert.equal(h.context.displayReady(),false);assert.equal(h.doc.notes[0].value,"  preserved\n ");
 console.log("zoom stub passed");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
