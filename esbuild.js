// Copyright (c) 2024 Antmicro <www.antmicro.com>
//
// SPDX-License-Identifier: Apache-2.0

const esbuild = require('esbuild');
const { polyfillNode } = require('esbuild-plugin-polyfill-node');

const production = process.argv.includes('--production');

function esbuildContext(entryPoint, outfile, browser) {
  return esbuild.context({
    entryPoints: [entryPoint],
    bundle: true,
    format: browser ? 'esm' : 'cjs',
    minify: production,
    sourcemap: !production,
    sourcesContent: false,
    platform: browser ? 'browser' : 'node',
    outfile,
    plugins: browser ? [polyfillNode({})] : [],
    packages: 'external',
  });
}

async function main() {
  const ctxMain = await esbuildContext('js-client/index.ts', 'dist/index.js');
  const ctxWeb = await esbuildContext(
    'js-client/index.ts',
    'dist/web.js',
    true,
  );

  const ctxs = [ctxMain, ctxWeb];

  await Promise.all(ctxs.map(ctx => ctx.rebuild()));
  await Promise.all(ctxs.map(ctx => ctx.dispose()));
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
