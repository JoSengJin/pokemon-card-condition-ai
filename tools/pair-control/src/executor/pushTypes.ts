export interface PushCommit { sha: string; parents: string; subject: string }

export interface Finding { kind: 'forbidden_path' | 'secret_pattern' | 'large_file'; file: string; line?: number; detail: string; commit?: string; fingerprint?: string; acknowledged?: boolean }

export interface PushPlan {
  id: string; remote: string; remoteUrl: string; branch: string; localHead: string; remoteHead: string | null;
  commits: PushCommit[]; files: string[]; tasks: string[]; findings: Finding[]; blockers: string[]; warnings: string[];
  dryRun: { ok: boolean; detail: string } | null; revertOf: string | null; checkedAt: string;
}

export interface RevertInfo { preparedAt: string; preHead: string; newHead: string; commits: string[]; treeRestored: boolean; pushedAs?: string }

export interface PushRecord {
  id: string; at: string; kind: 'push' | 'revert'; remote: string; remoteUrl: string; branch: string; preRemoteHead: string; pushedSha: string;
  commits: string[]; tasks: string[]; command: string[]; status: 'pushed_verified' | 'push_failed' | 'push_unverified' | 'remote_mismatch';
  detail: string; verifiedAt?: string; revertOf?: string; revert?: RevertInfo | null;
}
