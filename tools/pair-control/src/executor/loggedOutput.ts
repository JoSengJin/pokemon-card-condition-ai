import type { ChildProcessWithoutNullStreams } from 'node:child_process';
import type { lineWriter } from './logWriter.ts';

export function attachLoggedOutput(child: Pick<ChildProcessWithoutNullStreams, 'stdout' | 'stderr'>, writer: ReturnType<typeof lineWriter>) {
  child.stdout.on('data', (chunk) => writer.push(String(chunk)));
  child.stderr.on('data', (chunk) => writer.push(String(chunk)));
}
