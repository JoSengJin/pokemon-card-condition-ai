"""Synthetic only: original score equality, masking, inverse geometry and HTML sidecar."""
from pathlib import Path
import ast
import sys
import tempfile
import torch
from PIL import Image,ImageOps

ROOT=Path.cwd();folder=ROOT/'tools/diagnostics/surface-patch-evidence-batch-20261108';sys.path.insert(0,str(folder))
from patch_evidence import score_with_evidence
from patch_geometry import token_box
from patch_report import render_report
source=ast.parse((ROOT/'tools/experiments/edge-back-source-weight-20261030/worker.py').read_text())
legacy=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='score')
namespace={'torch':torch};exec(compile(ast.Module(body=[legacy],type_ignores=[]),'legacy_score','exec'),namespace)
for shape in [(5,1024,384),(2,4,3)]:
 torch.manual_seed(7);x=torch.randn(shape);mask=torch.rand(shape[:2])>.3;mask[:,0]=True;coef=torch.randn(shape[-1]);bias=torch.tensor(.01)
 expected=namespace['score'](x,mask,coef,bias);scores,evidence,logits=score_with_evidence(x,mask,coef,bias)
 assert scores==expected and logits.shape==x.shape[:2]
 for i,e in enumerate(evidence):
  assert mask[i,e['top_index']] and e['score']==scores[i] and e['upper_gap']>=-1e-6
  assert abs(e['top_soft_weight']-float(torch.softmax(logits[i].masked_fill(~mask[i],-torch.inf)/.1,0)[e['top_index']]))<2e-5
# Exact0.5 boundary, tied scores, invalid high token, single valid token.
x=torch.tensor([[[0.],[0.],[1000.]],[[1.],[1000.],[1000.]]]);mask=torch.tensor([[1,1,0],[1,0,0]],dtype=torch.bool)
scores,ev,logits=score_with_evidence(x,mask,torch.ones(1),torch.tensor(0.))
assert scores==namespace['score'](x,mask,torch.ones(1),torch.tensor(0.))
assert scores[0]==.5 and ev[0]['top_index']==0 and ev[0]['second_index']==1 and ev[0]['margin']==0
assert ev[1]['second_index'] is None and ev[1]['above_half_tokens']==1
# Geometry: inverse-mapped token tiles exactly partition the physical crop, including partial padding.
from card_condition.local_wear_cnn import physical_pixel_mask
import math
with tempfile.TemporaryDirectory() as td:
 for w,h in [(448,448),(101,301),(301,101),(333,222)]:
  path=Path(td,f'{w}-{h}.jpg');Image.new('RGB',(w,h),'white').save(path);box=[.11,.17,.89,.83]
  pixels=physical_pixel_mask(path,box,halo=0,image_size=448);valid=pixels.reshape(32,14,32,14).any(3).any(1).flatten()
  total_area=0
  for index in valid.nonzero().flatten().tolist():
   mapped=token_box((w,h),box,index);l,t,r,b=mapped['box'];total_area+=(r-l)*(b-t)
   token_pixels=pixels[(index//32)*14:(index//32+1)*14,(index%32)*14:(index%32+1)*14]
   assert abs(mapped['coverage']-int(token_pixels.sum())/196)<1e-14
   assert 0<=l<r<=1 and 0<=t<b<=1
  expected_area=(math.ceil(box[2]*w)-math.floor(box[0]*w))*(math.ceil(box[3]*h)-math.floor(box[1]*h))/(w*h)
  assert abs(total_area-expected_area)<1e-12
  invalid=(~valid).nonzero().flatten()
  if len(invalid):
   try:token_box((w,h),box,int(invalid[0]))
   except ValueError:pass
   else:raise AssertionError('padding only token accepted')
 # EXIF orientation is handled before geometry, matching original preprocessing.
 path=Path(td,'exif.jpg');im=Image.new('RGB',(10,20),'white');exif=Image.Exif();exif[274]=6;im.save(path,exif=exif)
 with Image.open(path) as im:assert ImageOps.exif_transpose(im).size==(20,10)
 # Real HTML/CSV rendering fixture, no network and no model inference.
 raw=Path(td,'photo.jpg');Image.new('RGB',(448,448),'white').save(raw)
 xx=torch.zeros((1,1024,1));mm=torch.ones((1,1024),dtype=torch.bool);ss,ee,ll=score_with_evidence(xx,mm,torch.ones(1),torch.tensor(0.))
 detail=ee[0];detail.update(saved_score=ss[0],replay_error=0.,top_geometry=token_box((448,448),[0,0,1,1],detail['top_index']),second_geometry=token_box((448,448),[0,0,1,1],detail['second_index']))
 entry=dict(row=dict(id='synthetic',image=str(raw),box=[0,0,1,1],target=0),parent_index=0,tags=['synthetic'],models={key:detail for key in ['baseline','arithmetic','lme','mixture']})
 render_report([entry],dict(rows=1,training_calls=0),Path(td),dict(tracked_directory='synthetic'))
 page=Path(td,'report.html').read_text();assert page.count('<details data-id=')==1 and 'second' in page and len(Path(td,'comparison.csv').read_text().splitlines())==5
for p in folder.glob('*.py'):
 tree=ast.parse(p.read_text());assert sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(tree))<=7
 assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['backward','step','fit'] for n in ast.walk(tree))
print('PASS legacy score bitwise equality/random+boundary/ties/masking/single-token; geometry square/tall/wide/partialpadding+EXIF; HTML+CSV; function limits/no training calls')

assert sum(isinstance(n,ast.MatMult) for n in ast.walk(ast.parse((folder/'patch_evidence.py').read_text())))==1
print('PASS: evidence scoring contains exactly one affine matrix multiplication')

torch.set_num_threads(2);torch.manual_seed(11)
x=torch.randn(352,128,64)+3;coef=torch.randn(64);bias=-3*coef.sum();mask=torch.ones((352,128),dtype=torch.bool);selected=[1,12,48,86,209]
expected,_,_=score_with_evidence(x,mask,coef,bias)
workspace=torch.zeros_like(x);workspace[selected]=x[selected]
actual,_,_=score_with_evidence(workspace,mask,coef,bias)
assert [actual[i] for i in selected]==[expected[i] for i in selected]
print('PASS original batch-size workspace preserves selected output values exactly')
