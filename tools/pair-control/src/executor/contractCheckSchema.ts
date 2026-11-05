import { z } from 'zod';
import { relPath } from './contractScopeSchema.ts';
import { CHECK_EXECUTABLES } from './contractConstants.ts';

export const DENIED_CHECK_ARGS = /experiment_record|cross_review|workspace_lock|(^|\s)(train|predict|infer)(\s|$)/;

export const CheckSpec = z.object({
  id: z.string().regex(/^[a-z0-9][a-z0-9_-]{0,31}$/),
  name: z.string().min(1).max(80),
  executable: z.enum(CHECK_EXECUTABLES),
  args: z.array(z.string().max(500).refine((a) => !a.includes('\0'))).max(40).default([]),
  cwd: relPath.default('.'),
}).superRefine((c, ctx) => {
  if (DENIED_CHECK_ARGS.test(c.args.join(' '))) ctx.addIssue({ code: 'custom', message: `검사 '${c.name}': 학습·실험·자동 검토 진입점은 검사로 실행할 수 없음`, path: ['args'] });
});

export type CheckSpecT = z.infer<typeof CheckSpec>;
