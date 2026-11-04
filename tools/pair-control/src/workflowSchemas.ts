import { z } from 'zod';

export const Flow = z.object({
  taskId: z.string(),
  reviewOnly: z.boolean().optional(),
  execId: z.string().nullable().optional(),
  exitCode: z.number().nullable().optional(),
  cancelled: z.boolean().optional(),
  manual: z.boolean().optional(),
  headSha: z.string().nullable().optional(),
  checksPassed: z.boolean().optional(),
  outcome: z.string().optional(),
  detail: z.string().optional(),
});
export type FlowT = z.infer<typeof Flow>;

export const Prepared = z.object({
  ok: z.boolean(),
  taskId: z.string().optional(),
  createWorktree: z.boolean().optional(),
  task: z.any().optional(),
  detail: z.string().optional(),
});
