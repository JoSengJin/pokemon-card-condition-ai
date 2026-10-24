const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../artifacts/edge-contrast-confirmed-20261021/point3-review/index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const clone=x=>JSON.parse(JSON.stringify(x));
const initial=()=>({revision:'r1',token:'old-token',rows:[{id:'case3',back:'/photo.jpg',notes:'preserve',side_annotations:{back:{labels:{edge_defect:1},defect_points:[]}}}]});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function app(storage=new Map()){
  let fetchImpl=async()=>({ok:true,json:async()=>clone(initial())});
  const ctx2d={drawImage(){},beginPath(){},arc(){},stroke(){}};
  const canvas={getContext:()=>ctx2d,getBoundingClientRect:()=>({left:0,top:0,width:432,height:1152})};
  const save={disabled:true},status={},title={};
  class Image {constructor(){this.naturalWidth=810;this.naturalHeight=1080;}set src(value){this.onload();}}
  const context=vm.createContext({document:{querySelector:s=>({'#c':canvas,'#save':save,'#status':status,'#title':title}[s])},Image,structuredClone:clone,fetch:(...args)=>fetchImpl(...args),localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}});
  vm.runInContext(script,context);await flush();
  return {canvas,save,status,storage,select(){canvas.onclick({clientX:180,clientY:400});},setFetch(fn){fetchImpl=fn;},point(){return clone(vm.runInContext('point',context));}};
}
test('save obtains fresh token after server restart and preserves other fields',async()=>{
  const a=await app();a.select();const selected=a.point();let posts=0;
  a.setFetch(async(url,options)=>{
    if(url==='/api/review')return {ok:true,json:async()=>({...initial(),token:'new-token'})};
    posts++;assert.equal(options.headers['X-Review-Token'],'new-token');
    const body=JSON.parse(options.body);assert.equal(body.revision,'r1');assert.equal(body.rows[0].notes,'preserve');
    assert.deepEqual(body.rows[0].side_annotations.back.defect_points,[selected]);
    return {ok:true,json:async()=>({...initial(),revision:'r2',rows:body.rows})};
  });
  await a.save.onclick();assert.equal(posts,1);assert.equal(a.storage.size,0);assert.match(a.status.textContent,/저장 완료/);
});
test('connection failure retains the selected point across reload',async()=>{
  const storage=new Map();const a=await app(storage);a.select();const selected=a.point();
  a.setFetch(async()=>{throw new Error('connection refused');});await a.save.onclick();
  assert.equal(a.save.disabled,false);assert.equal(storage.size,1);assert.deepEqual(a.point(),selected);
  const reloaded=await app(storage);assert.deepEqual(reloaded.point(),selected);assert.equal(reloaded.save.disabled,false);assert.match(reloaded.status.textContent,/복구/);
});
test('concurrent revision change never posts over newer annotations',async()=>{
  const a=await app();a.select();let posts=0;
  a.setFetch(async url=>{if(url!=='/api/review')posts++;return {ok:true,json:async()=>({...initial(),revision:'other-edit'})};});
  await a.save.onclick();assert.equal(posts,0);assert.equal(a.storage.size,1);assert.match(a.status.textContent,/덮어쓰지/);
});
test('an already committed identical point is acknowledged without reposting',async()=>{
  const a=await app();a.select();const s=initial();s.revision='r2';s.rows[0].side_annotations.back.defect_points=[a.point()];let posts=0;
  a.setFetch(async url=>{if(url!=='/api/review')posts++;return {ok:true,json:async()=>s};});
  await a.save.onclick();assert.equal(posts,0);assert.equal(a.storage.size,0);assert.match(a.status.textContent,/이미 저장/);
});
test('saving locks point editing until the pending request completes',async()=>{
  const a=await app();a.select();const selected=a.point();let release;
  a.setFetch(()=>new Promise(resolve=>{release=resolve;}));const pending=a.save.onclick();
  a.canvas.onclick({clientX:300,clientY:600});assert.deepEqual(a.point(),selected);
  release({ok:true,json:async()=>({...initial(),revision:'conflict'})});await pending;
});
