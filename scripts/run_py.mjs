import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const candidates = process.platform === 'win32' ? ['python', 'py', 'python3'] : ['python3', 'python'];

for (const cmd of candidates) {
  const probe = spawnSync(cmd, ['--version'], { stdio: 'ignore' });
  if (probe.status === 0) {
    const res = spawnSync(cmd, args, { stdio: 'inherit' });
    process.exit(res.status ?? 1);
  }
}

console.error('Error: Could not find Python (python3 / python) in PATH.');
process.exit(1);

