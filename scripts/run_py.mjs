import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const args = process.argv.slice(2);
const isWin = process.platform === 'win32';
const venvCandidates = isWin
  ? [join(process.cwd(), '.venv', 'Scripts', 'python.exe'), join(process.cwd(), 'venv', 'Scripts', 'python.exe')]
  : [join(process.cwd(), '.venv', 'bin', 'python3'), join(process.cwd(), 'venv', 'bin', 'python3')];

const candidates = [
  ...venvCandidates.filter(p => existsSync(p)),
  ...(isWin ? ['python', 'py', 'python3'] : ['python3', 'python']),
];

for (const cmd of candidates) {
  const probe = spawnSync(cmd, ['--version'], { stdio: 'ignore' });
  if (probe.status === 0) {
    const res = spawnSync(cmd, args, { stdio: 'inherit' });
    process.exit(res.status ?? 1);
  }
}

console.error('Error: Could not find Python (python3 / python) in PATH.');
process.exit(1);
