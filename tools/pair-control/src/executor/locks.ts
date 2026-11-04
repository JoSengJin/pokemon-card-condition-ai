// O_EXCL 잠금 파일. 같은 task/worktree/통합의 중복 실행을 프로세스·재시작을 넘어 차단한다.
// 해제는 종료가 확인된 경우나 사용자가 결과 불명을 확정한 경우에만 한다(자동 만료 없음).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export class LockDir {
  constructor(private dir: string) { fs.mkdirSync(dir, { recursive: true }); }

  /** 성공 시 true. 이미 있으면 false(소유자 정보는 holder로 확인). */
  acquire(name: string, owner: Record<string, unknown>): boolean {
    try {
      const safe = name.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 80);
      const hash = crypto.createHash('sha256').update(name).digest('hex').slice(0, 12);
      const fd = fs.openSync(path.join(this.dir, `${safe}-${hash}.lock`), 'wx');
      fs.writeSync(fd, JSON.stringify({ name, ...owner, at: new Date().toISOString() }));
      fs.closeSync(fd);
      return true;
    } catch (err: any) {
      if (err.code === 'EEXIST') return false;
      throw err;
    }
  }

  holder(name: string): Record<string, unknown> | null {
    const safe = name.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 80);
    const hash = crypto.createHash('sha256').update(name).digest('hex').slice(0, 12);
    try { return JSON.parse(fs.readFileSync(path.join(this.dir, `${safe}-${hash}.lock`), 'utf8')); } catch { return null; }
  }

  /** 소유자가 일치할 때만 해제한다. */
  release(name: string, ownerKey: string, ownerValue: string) {
    const safe = name.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 80);
    const hash = crypto.createHash('sha256').update(name).digest('hex').slice(0, 12);
    const file = path.join(this.dir, `${safe}-${hash}.lock`);
    let h: Record<string, unknown> | null = null;
    try { h = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { /* 잠금 없음 */ }
    if (h && h[ownerKey] === ownerValue) fs.rmSync(file, { force: true });
  }
}
