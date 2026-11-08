"""Synthetic process output only; no model inputs/inference/training."""
from pathlib import Path
import os,subprocess,sys,tempfile,time,ast
child="import os,sys,time; print('CHILD_STDOUT'); print('CHILD_STDERR',file=sys.stderr); print('UNBUFFERED='+os.environ['PYTHONUNBUFFERED']); time.sleep(2)"
parent="import subprocess,sys; print('PARENT_STDOUT'); print('PARENT_STDERR',file=sys.stderr); p=subprocess.Popen([sys.executable,'-c',"+repr(child)+"],start_new_session=True); p.wait(); print('PARENT_DONE')"
with tempfile.TemporaryDirectory() as directory:
 log=Path(directory)/'console.log'
 with log.open('xb') as stream:
  process=subprocess.Popen([sys.executable,'-c',parent],env=dict(os.environ,PYTHONUNBUFFERED='1'),stdout=stream,stderr=stream)
  try:
   deadline=time.monotonic()+5
   while time.monotonic()<deadline:
    text=log.read_text()
    if all(marker in text for marker in ['PARENT_STDOUT','PARENT_STDERR','CHILD_STDOUT','CHILD_STDERR','UNBUFFERED=1']):break
    time.sleep(.02)
   assert all(marker in text for marker in ['PARENT_STDOUT','PARENT_STDERR','CHILD_STDOUT','CHILD_STDERR','UNBUFFERED=1']),text
   assert process.poll() is None,'Output must be persisted while process still running'
   assert process.wait(timeout=5)==0 and 'PARENT_DONE' in log.read_text()
  finally:
   if process.poll() is None:process.kill();process.wait()
 try:log.open('xb')
 except FileExistsError:pass
 else:raise AssertionError('Must refuse to overwrite existing console')
assert sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(Path(__file__).read_text())))==0
print('PASS: parent+child stdout/stderr inherited into unique log; PYTHONUNBUFFERED=1 visible; persisted before exit; existing log not overwritten; no extra project call layer')
