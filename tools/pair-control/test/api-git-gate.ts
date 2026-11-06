// 임시 git wrapper. 지정한 cwd/인자 준비 단계만 멈추며 실제 git 동작은 그대로 전달한다.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';

export function gitGate(cwd:string,prefix:string[],nth=1){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pair-api-gate-')),entered=path.join(dir,'entered'),release=path.join(dir,'release'),count=path.join(dir,'count');
 const original=process.env.PATH,real=execFileSync('/usr/bin/which',['git'],{encoding:'utf8'}).trim();
 const binary=path.join(dir,'git');
 fs.writeFileSync(binary,`#!${process.execPath}\nimport fs from 'node:fs';import {spawnSync} from 'node:child_process';import {setTimeout as delay} from 'node:timers/promises';
const a=process.argv.slice(2),prefix=${JSON.stringify(prefix)};
if(process.cwd()===${JSON.stringify(cwd)}&&prefix.every((v,i)=>a[i]===v)){const n=(fs.existsSync(${JSON.stringify(count)})?Number(fs.readFileSync(${JSON.stringify(count)},'utf8')):0)+1;fs.writeFileSync(${JSON.stringify(count)},String(n));if(n===${nth}){fs.writeFileSync(${JSON.stringify(entered)},'entered');while(!fs.existsSync(${JSON.stringify(release)}))await delay(10);}}
const r=spawnSync(${JSON.stringify(real)},a,{cwd:process.cwd(),env:process.env});process.stdout.write(r.stdout??'');process.stderr.write(r.stderr??'');process.exit(r.status??1);
`);fs.chmodSync(binary,0o755);process.env.PATH=dir+path.delimiter+original;
 return {entered,release,close(){fs.writeFileSync(release,'continue');process.env.PATH=original;fs.rmSync(dir,{recursive:true,force:true});}};
}
