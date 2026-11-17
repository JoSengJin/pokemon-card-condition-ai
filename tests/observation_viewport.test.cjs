"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const {makeHarness}=require("./observation_browser_fixture.cjs");
async function main(){
 const page=fs.readFileSync(process.argv[2],"utf8"),h=makeHarness(page);
 for(const id of ["collection-contract","collection-out","collection-export"])h.doc.elements.set(id,{textContent:id==="collection-contract"?page.match(/<script id="collection-contract" type="application\/json">([^]*?)<\/script>/)[1]:"",value:"",addEventListener(){}});
 for(const id of ["viewport-code","collection-response-code"])vm.runInContext(page.match(new RegExp('<script id="'+id+'">([^]*?)<\\/script>'))[1],h.context);
 h.context.attachResponseControls();h.context.attachViewport();await h.context.initialize();
 assert.equal(h.context.matchesViewport({viewport_css:null,image_css:null,device_pixel_ratio:null},h.context.readViewport()),true);
 assert.equal(h.context.readViewport().visual,null);
 h.context.exportCollection();const body=JSON.parse(h.doc.getElementById("collection-out").value);
 assert.equal(body.schema_version,2);assert.equal(body.human_truth,false);assert.equal(body.eligible_for_collection,false);
 assert.equal(body.viewport_events.at(-1).event,"export");assert.equal(body.base_response.observations.events.at(-1).event,"export");
 h.doc.notes[0].value="  unchanged\n ";h.context.window.innerHeight=0;h.context.observeViewport({type:"resize"});
 h.context.window.innerHeight=600;h.context.observeViewport({type:"resize"});
 assert.equal(h.context.displayReady(),false);assert.equal(h.doc.answers[0].disabled,true);assert.equal(h.doc.notes[0].value,"  unchanged\n ");
 console.log("viewport stub passed");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
