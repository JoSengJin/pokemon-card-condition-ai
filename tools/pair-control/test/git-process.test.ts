import assert from 'node:assert/strict';
import { test } from 'node:test';
import { run } from '../src/executor/gitProcess.ts';

test('명령 IO는 성공·종료코드·출력·환경을 보존하고 spawn 실패·시간 초과를 거절 대신 결과로 반환한다', async () => {
  const success = await run(process.execPath, ['-e', 'process.stdout.write(process.env.PAIR_PROCESS_FIXTURE);process.stderr.write("notice")'], process.cwd(), 10_000, { PAIR_PROCESS_FIXTURE: 'fixture' });
  assert.deepEqual(success, { code: 0, stdout: 'fixture', stderr: 'notice' });
  const failed = await run(process.execPath, ['-e', 'process.stdout.write("partial");process.stderr.write("failure");process.exit(23)'], process.cwd());
  assert.deepEqual(failed, { code: 23, stdout: 'partial', stderr: 'failure' });
  const missing = await run('/nonexistent/pair-control-fixture', [], process.cwd());
  assert.equal(missing.code, 1); assert.equal(missing.stdout, '');
  const timed = await run(process.execPath, ['-e', 'setInterval(()=>{},1000)'], process.cwd(), 40);
  assert.equal(timed.code, 1);
});
