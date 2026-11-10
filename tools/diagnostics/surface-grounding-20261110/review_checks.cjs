"use strict";
const assert = require("node:assert/strict");
const {pointFromClick, validateAnswers} = require("./review.js");
const row = {id:"card/back/surface/center", image_sha256:"hash", target:1, box:[.2,.3,.6,.9]};
const packet = {packet_id:"packet", entries:[{row,selected:true,known_points:[]}]};
const point = pointFromClick(row,{left:100,top:20,width:200,height:300},200,170);
assert.ok(Math.abs(point.x-.4)<1e-14 && Math.abs(point.y-.6)<1e-14);
assert.deepEqual(pointFromClick(row,{left:100,top:20,width:200,height:300},100,20),{x:.2,y:.3,label:"surface_defect"});
const answer = {schema_version:1,kind:"surface_grounding_human_evidence",packet_id:"packet",responses:[{id:row.id,image_sha256:"hash",target:1,status:"located",point,category:"surface_mark",note:"  원문\n<script>메모</script>  "}]};
assert.equal(validateAnswers(packet,answer).responses[0].note,answer.responses[0].note);
const unknown=structuredClone(answer);unknown.responses[0].status="cannot_localize";unknown.responses[0].point=null;unknown.responses[0].category="unclear";
assert.equal(validateAnswers(packet,unknown).responses[0].point,null);
assert.equal(validateAnswers(packet,{...answer,responses:[]}).responses.length,0);
const bads=[];
let bad=structuredClone(answer);bad.packet_id="other";bads.push(bad);
bad=structuredClone(answer);bad.responses[0].target=0;bads.push(bad);
bad=structuredClone(answer);bad.responses[0].target=true;bads.push(bad);
bad=structuredClone(answer);bad.responses.push(bad.responses[0]);bads.push(bad);
bad=structuredClone(answer);bad.responses[0].point.x=.9;bads.push(bad);
bad=structuredClone(answer);bad.responses[0].point.x=NaN;bads.push(bad);
bad=structuredClone(answer);bad.responses[0].point.x=true;bads.push(bad);
bad=structuredClone(answer);bad.responses[0].point.label="edge_defect";bads.push(bad);
bad=structuredClone(answer);bad.responses[0].id="unknown";bads.push(bad);
bad=structuredClone(answer);bad.responses[0].image_sha256="other";bads.push(bad);
bad=structuredClone(answer);bad.responses[0].new_target=0;bads.push(bad);
bad=structuredClone(answer);bad.responses[0].status="";bads.push(bad);
bad=structuredClone(unknown);bad.responses[0].point=point;bads.push(bad);
for(const a of bads){let rejected=false;try{validateAnswers(packet,a);}catch{rejected=true;}assert.ok(rejected);}
for(const p of [{...packet,entries:[{row,selected:false,known_points:[]}]},{...packet,entries:[{row,selected:true,known_points:[point]}]}]){let rejected=false;try{validateAnswers(p,answer);}catch{rejected=true;}assert.ok(rejected);}
let rejected=false;try{pointFromClick(row,{left:100,top:20,width:200,height:300},99,50);}catch{rejected=true;}assert.ok(rejected);
const normal=structuredClone(packet);normal.entries[0].row.target=0;
const normalAnswer=structuredClone(answer);normalAnswer.responses[0].target=0;normalAnswer.responses[0].category="print_pattern";normalAnswer.responses[0].point.label="normal_explanation";
assert.equal(validateAnswers(normal,normalAnswer).responses[0].point.label,"normal_explanation");
console.log("PASS: JavaScript crop-coordinate mapping; explicit/unknown/normal explanations; exact note export; packet/truth/kind/bounds/duplicate/existing-evidence guards");


async function checkDownload() {
  const fs = require("node:fs"), vm = require("node:vm");
  const context = vm.createContext({module:{exports:{}}, Blob, URL});
  vm.runInContext(fs.readFileSync(require.resolve("./review.js"), "utf8"), context);
  const nodes = {export:{value:""}, answered:{textContent:""}, download:{dataset:{}, attrs:{},
    setAttribute(name,value){this.attrs[name]=value;},
    removeAttribute(name){delete this.attrs[name];delete this[name];}}};
  context.document = {getElementById(id){return nodes[id];}};
  context.fixturePacket = packet; context.fixtureResponses = {[row.id]:answer.responses[0]};
  vm.runInContext("packet=fixturePacket; responses=fixtureResponses; refreshExport();", context);
  const url = nodes.download.href;
  assert.ok(url.startsWith("blob:")); assert.equal(nodes.download.download,"surface-grounding-packet-1.json");
  assert.equal(nodes.download.attrs["aria-disabled"],"false"); assert.equal(nodes.download.tabIndex,0);
  const payload = JSON.parse(await (await fetch(url)).text());
  assert.deepEqual(payload, answer); assert.equal(payload.responses[0].note,answer.responses[0].note);
  context.fixturePacket = {...packet,batch_name:"01"};
  vm.runInContext("packet=fixturePacket; refreshExport();", context);
  assert.equal(nodes.download.download,"surface-grounding-packet-01-1.json");
  context.fixtureResponses = {};
  vm.runInContext("responses=fixtureResponses; refreshExport();", context);
  assert.equal(nodes.download.href,undefined); assert.equal(nodes.download.attrs["aria-disabled"],"true");
  assert.equal(nodes.download.tabIndex,-1); assert.equal(nodes.answered.textContent,"0");
  let revoked=false;try{await fetch(url);}catch{revoked=true;}assert.ok(revoked);
  console.log("PASS: native Blob JSON download preserves exact UTF-8 responses and packet,filename/count; empty export disabled; previous URL revoked");
}
checkDownload().catch(error => {console.error(error);process.exitCode=1;});

const fractionalRow={...row,box:[.201,.301,.599,.899]};
const croppedPoint=pointFromClick(fractionalRow,{left:50,top:20,width:292,height:314},196,177,[.2,.3,.6,.9]);
assert.ok(Math.abs(croppedPoint.x-.4)<1e-14 && Math.abs(croppedPoint.y-.6)<1e-14);
let edgeRejected=false;try{pointFromClick(fractionalRow,{left:50,top:20,width:292,height:314},50,20,[.2,.3,.6,.9]);}catch{edgeRejected=true;}assert.ok(edgeRejected);
const projected={kind:"surface_grounding_display_projection",packet_id:packet.packet_id,entries:packet.entries};
assert.equal(validateAnswers(projected,answer).packet_id,packet.packet_id);
console.log("PASS: native integer-crop bounds invert to original normalized coordinates; outside original region rejected; projected packet retains answer binding");
