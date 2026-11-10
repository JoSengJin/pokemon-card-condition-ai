"use strict";
const assert=require("node:assert/strict"),vm=require("node:vm"),fs=require("node:fs");
const script=fs.readFileSync(require.resolve("./review.js"),"utf8"),listeners=new Map(),registrations={},markers=[];
const packet={packet_id:"synthetic",entries:[{id:"region/point-review/1",row:{id:"region",target:1,image_sha256:"photo",box:[.2,.3,.6,.9]},completed:false}]};
const fields={dataset:{},disabled:true,querySelectorAll:lookup};
const card={dataset:{index:"0"},querySelector:lookup,querySelectorAll:lookup};
const image={kind:"image",inCard:true,nodeType:1,dataset:{viewBox:".2,.3,.6,.9"},closest,getBoundingClientRect:bounds,parentElement:{querySelector:lookup}};
const normal={kind:"button",inCard:true,nodeType:1,dataset:{judgment:"normal"},attrs:{},setAttribute,closest};
const defect={...normal,dataset:{judgment:"defect"},attrs:{}};
const unknown={...normal,dataset:{judgment:"unknown"},attrs:{}};
const record={...normal,dataset:{action:"record"}},edit={...normal,dataset:{action:"edit"},hidden:true};
const layer={querySelector:lookup,appendChild:Array.prototype.push.bind(markers)};
const nodes={packet:{textContent:JSON.stringify(packet)},"input-status":{textContent:"pending",dataset:{state:"pending"}},copy:{disabled:true},export:{value:""},answered:{textContent:""},message:{textContent:""},download:{dataset:{},attrs:{},setAttribute,removeAttribute:setAttribute},
 'fieldset':fields,'img[data-locate]':image,'.point-layer':layer,'[name="x"]':{value:""},'[name="y"]':{value:""},'[name="note"]':{value:"  원문\n그대로  "},'.response-state':{textContent:""},'[data-action="edit"]':edit};
function lookup(key){
 if(key==='[data-requires-js]')return[fields,nodes.copy];
 if(key==='button[data-judgment]')return[normal,defect,unknown];
 if(key==='.new-point')return markers[0]||null;
 return nodes[key];
}
function closest(selector){if(selector==='button')return this.kind==='button'?this:null;if(selector==='img[data-locate]')return this.kind==='image'?this:null;if(selector==='article[data-index]')return this.inCard?card:null;return null;}
function setAttribute(key,value){if(arguments.length===1){delete this.attrs[key];delete this[key];return;}this.attrs[key]=value;}
function createElement(){return{attrs:{},style:{},setAttribute,remove:Array.prototype.pop.bind(markers)};}
function register(type,handler,options){listeners.set(type,handler);registrations[type]=options;}
function bounds(){return{left:10,top:20,width:200,height:300};}
const document={getElementById:lookup,querySelectorAll:lookup,addEventListener:register,createElement};
const context=vm.createContext({document,module:{exports:{}},URL,Blob});vm.runInContext(script,context);
assert.equal(nodes['input-status'].dataset.state,'ready');assert.equal(fields.disabled,false);assert.equal(nodes.copy.disabled,false);
for(const type of ['click','change','pointerdown','pointermove','pointerup','pointercancel']){assert.ok(listeners.has(type));assert.equal(registrations[type],true);}
listeners.get('click')({type:'click',target:defect,timeStamp:1});assert.equal(fields.dataset.judgment,'defect');assert.equal(defect.attrs['aria-pressed'],'true');
listeners.get('pointerdown')({type:'pointerdown',target:image,pointerId:1,isPrimary:true,clientX:110,clientY:170,timeStamp:10});
listeners.get('pointerup')({type:'pointerup',target:image,pointerId:1,isPrimary:true,clientX:110,clientY:170,timeStamp:50});
assert.ok(Math.abs(Number(nodes['[name="x"]'].value)-.4)<1e-14);assert.ok(Math.abs(Number(nodes['[name="y"]'].value)-.6)<1e-14);assert.equal(markers.length,1);
assert.ok(Math.abs(parseFloat(markers[0].style.left)-50)<1e-10);assert.ok(Math.abs(parseFloat(markers[0].style.top)-50)<1e-10);
listeners.get('click')({type:'click',target:image,clientX:150,clientY:200,timeStamp:60});assert.ok(Math.abs(Number(nodes['[name="x"]'].value)-.4)<1e-14);
listeners.get('pointerdown')({type:'pointerdown',target:image,pointerId:2,isPrimary:true,clientX:110,clientY:170,timeStamp:100});
listeners.get('pointermove')({type:'pointermove',target:image,pointerId:2,clientX:170,clientY:210,timeStamp:120});
listeners.get('pointerup')({type:'pointerup',target:image,pointerId:2,isPrimary:true,clientX:110,clientY:170,timeStamp:150});assert.ok(Math.abs(Number(nodes['[name="x"]'].value)-.4)<1e-14);
listeners.get('click')({type:'click',target:image,clientX:150,clientY:200,timeStamp:160});assert.ok(Math.abs(Number(nodes['[name="x"]'].value)-.4)<1e-14);
listeners.get('pointerdown')({type:'pointerdown',target:image,pointerId:3,isPrimary:true,clientX:110,clientY:170,timeStamp:200});
listeners.get('pointercancel')({type:'pointercancel',target:image,pointerId:3,timeStamp:230});
listeners.get('click')({type:'click',target:image,clientX:150,clientY:200,timeStamp:240});assert.ok(Math.abs(Number(nodes['[name="x"]'].value)-.4)<1e-14);
listeners.get('pointerdown')({type:'pointerdown',target:image,pointerId:4,isPrimary:true,clientX:150,clientY:200,timeStamp:300});
listeners.get('pointerup')({type:'pointerup',target:image,pointerId:4,isPrimary:true,clientX:150,clientY:200,timeStamp:1200});assert.ok(Math.abs(Number(nodes['[name="x"]'].value)-.4)<1e-14);
listeners.get('click')({type:'click',target:{nodeType:3,parentElement:image},clientX:150,clientY:200,timeStamp:2200});assert.ok(Math.abs(Number(nodes['[name="x"]'].value)-.48)<1e-14);
listeners.get('click')({type:'click',target:record,timeStamp:2300});const saved=JSON.parse(nodes.export.value);
assert.equal(saved.responses.length,1);assert.equal(saved.responses[0].judgment,'defect');assert.equal(saved.responses[0].note,'  원문\n그대로  ');assert.equal(fields.disabled,true);
listeners.get('click')({type:'click',target:edit,timeStamp:2400});assert.equal(fields.disabled,false);assert.equal(JSON.parse(nodes.export.value).responses.length,0);
listeners.get('click')({type:'click',target:unknown,timeStamp:2500});listeners.get('click')({type:'click',target:record,timeStamp:2600});
assert.equal(JSON.parse(nodes.export.value).responses[0].point,null);assert.equal(markers.length,0);
fields.disabled=true;nodes.copy.disabled=true;nodes.packet.textContent='{';listeners.clear();nodes['input-status'].dataset.state='pending';
vm.runInNewContext(script,{document,module:{exports:{}},URL,Blob});assert.equal(nodes['input-status'].dataset.state,'error');assert.equal(fields.disabled,true);assert.equal(nodes.copy.disabled,true);assert.equal(listeners.size,0);
console.log('PASS: actual JS startup→button→pointer tap→record→JSON;drag-return/cancel/longpress ignored;duplicateclick suppressed;click-only/text-node fallback;unknown not truth;invalidboot remains disabled and reports error');
