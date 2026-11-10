"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const {validateAnswers,pointFromClick}=require("./review.js");
const row={id:"region",image_sha256:"image",target:0,box:[.2,.3,.6,.9]};
const packet={packet_id:"packet",batch_name:"02",entries:[{id:"region/point-review/1",row,completed:false}]};
const response={id:packet.entries[0].id,image_sha256:"image",region_target:0,judgment:"defect",point:{x:.4,y:.6},note:"  한글\n<script>그대로</script>  "};
const answers={schema_version:1,kind:"surface_point_review_answers",packet_id:"packet",responses:[response]};
assert.equal(validateAnswers(packet,answers).responses[0].judgment,"defect");
const unknown=structuredClone(answers);unknown.responses[0].judgment="unknown";unknown.responses[0].point=null;
assert.equal(validateAnswers(packet,unknown).responses[0].point,null);
const normal=structuredClone(answers);normal.responses[0].judgment="normal";assert.equal(validateAnswers(packet,normal).responses.length,1);
assert.equal(validateAnswers(packet,{...answers,responses:[]}).responses.length,0);
const bads=[];
for(const [field,value] of [["region_target",1],["region_target",true],["judgment",""],["image_sha256","other"],["id","other"],["note",null]]){const a=structuredClone(answers);a.responses[0][field]=value;bads.push(a);}
for(const value of [NaN,true,2]){const a=structuredClone(answers);a.responses[0].point.x=value;bads.push(a);}
let a=structuredClone(answers);a.responses[0].point=null;bads.push(a);
a=structuredClone(unknown);a.responses[0].point=response.point;bads.push(a);
a=structuredClone(answers);a.responses.push(a.responses[0]);bads.push(a);
a=structuredClone(answers);a.responses[0].target=1;bads.push(a);
a=structuredClone(answers);a.packet_id="other";bads.push(a);
for(const value of bads){let rejected=false;try{validateAnswers(packet,value);}catch{rejected=true;}assert.ok(rejected);}
let rejected=false;try{validateAnswers({...packet,entries:[{...packet.entries[0],completed:true}]},answers);}catch{rejected=true;}assert.ok(rejected);
const point=pointFromClick(row,{left:10,top:20,width:200,height:300},110,170);
assert.ok(Math.abs(point.x-.4)<1e-14&&Math.abs(point.y-.6)<1e-14);

async function uiChecks(){
 const context=vm.createContext({module:{exports:{}},URL,Blob});vm.runInContext(fs.readFileSync(require.resolve("./review.js"),"utf8"),context);
 const nodes={export:{value:"",focus:noop,select:noop,setSelectionRange:noop},answered:{textContent:""},message:{textContent:""},download:{dataset:{},attrs:{},setAttribute(key,value){this.attrs[key]=value;},removeAttribute(key){delete this.attrs[key];delete this[key];}}};
 function lookup(key){if(key==="button")return{id:"copy"};if(key==="article[data-index]")return null;return nodes[key];}
 let copyCalls=0;context.document={getElementById:lookup,execCommand(command){assert.equal(command,"copy");copyCalls++;return false;}};
 context.fixturePacket=packet;context.fixtureResponses={[response.id]:response};
 vm.runInContext("packet=fixturePacket;responses=fixtureResponses;refreshExport();",context);
 const payload=JSON.parse(await(await fetch(nodes.download.href)).text());assert.deepEqual(payload,answers);
 assert.ok(nodes.download.download.includes("02-1.json"));assert.equal(payload.responses[0].note,response.note);
 context.event={target:{closest:lookup}};vm.runInContext("handleClick(event)",context);assert.equal(copyCalls,1);assert.ok(nodes.message.textContent.includes("길게"));assert.equal(JSON.parse(nodes.export.value).responses.length,1);
 const url=nodes.download.href;context.fixtureResponses={};vm.runInContext("responses=fixtureResponses;refreshExport();",context);
 assert.equal(nodes.download.attrs["aria-disabled"],"true");assert.equal(nodes.download.href,undefined);
 let revoked=false;try{await fetch(url);}catch{revoked=true;}assert.ok(revoked);
 console.log("PASS: tri-state explicit human point answers,unknown not binary,readonly region/completed guards;native coordinate;execCommand fallback+visible JSON;UTF-8 Blob export");
}
function noop(){}
uiChecks().catch(error=>{console.error(error);process.exitCode=1;});
