import process from 'node:process';

const version = process.versions.node;
const [major] = version.split('.').map((part) => Number(part));

if (Number.isNaN(major)) {
  console.error(`Unable to parse Node version: ${version}`);
  process.exit(1);
}

if (major > 20) {
  console.error(`Node ${major} detected. ts-node incompatible. Install Node 20 via NVM.`);
  process.exit(1);
}

if (major < 20) {
  console.warn(`Node ${version} detected. Recommended Node 20 for tooling compatibility.`);
}
