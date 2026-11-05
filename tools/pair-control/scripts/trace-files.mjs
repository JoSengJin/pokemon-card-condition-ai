import fs from 'node:fs';
import path from 'node:path';
import { stripTypeScriptTypes } from 'node:module';
import * as acorn from 'acorn';
import { MODIFIERS } from './trace-config.mjs';

export function option(args, name) {
  for (const arg of args) if (arg.startsWith('--' + name + '=')) return arg.slice(name.length + 3);
  return '';
}

export function listFiles(root, explicit) {
  if (explicit) return explicit.split(',').filter(Boolean);
  const out = [], pending = ['src'];
  while (pending.length) {
    const dir = pending.pop();
    for (const entry of fs.readdirSync(path.join(root, dir), { withFileTypes: true })) {
      const rel = path.join(dir, entry.name);
      if (entry.isDirectory()) pending.push(rel); else if (/\.(ts|js|mjs)$/.test(entry.name)) out.push(rel);
    }
  }
  if (fs.existsSync(path.join(root, 'scripts'))) for (const entry of fs.readdirSync(path.join(root, 'scripts'))) if (entry.endsWith('.mjs')) out.push(path.join('scripts', entry));
  return out.sort();
}

export function parseFiles(ctx) {
  for (const file of ctx.files) {
    const original = fs.readFileSync(path.join(ctx.root, file), 'utf8');
    const text = original.replace(MODIFIERS, (match) => ' '.repeat(match.length));
    const code = file.endsWith('.ts') ? stripTypeScriptTypes(text, { mode: 'strip' }) : text;
    ctx.parsed[file] = { orig: text, ast: acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'module', allowHashBang: true, locations: true }) };
  }
}
