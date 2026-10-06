import { transformSync } from 'esbuild'
import { readFileSync } from 'node:fs'
import Module from 'node:module'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const code = `
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import assert from 'node:assert/strict';
import App from './src/App.jsx';
import VideoTimeline from './src/components/ui/VideoTimeline.jsx';
import ScanNotes from './src/components/ui/ScanNotes.jsx';
import { mediaUrl } from './src/api/client.js';
const scan = { id: 'abc123', filename: 'a & b.jpg', media_token: 'private-token' };
assert.equal(mediaUrl(scan), 'https://api.example.test/api/scans/abc123/media/original?token=private-token');
assert.equal(mediaUrl(scan, 'thumbnail.jpg'), 'https://api.example.test/api/scans/abc123/media/thumbnail.jpg?token=private-token');
const timeline = renderToStaticMarkup(<VideoTimeline entries={[
  {index:0,time:1.5,fake_probability:0.85,classified:true},
  {index:1,time:2,fake_probability:0.1,classified:true},
  {index:2,time:3,fake_probability:0.5,classified:false}
]} />);
assert.ok(timeline.includes('85% fake model score'));
assert.ok(timeline.includes('No classification'));
assert.ok(timeline.includes('1.5s'));
assert.ok(!timeline.includes('undefined') && !timeline.includes('NaN'));
const notes = renderToStaticMarkup(<ScanNotes warnings={['Detailed research limitation']} isVideo />);
assert.ok(notes.includes('Results can be wrong') && notes.includes('sampled frames only'));
assert.ok(notes.includes('<details') && !notes.includes('<details open'));
assert.ok(notes.includes('Detailed research limitation'));
for (const [path, expected] of [['/','Scan Your Media'],['/history','Your Scan History'],['/privacy','Privacy Policy'],['/terms','Terms of Service']]) {
 const html = renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
 assert.ok(html.includes(expected), path + ' did not render expected content');
 if (path === '/') {
   for (const obsolete of ['Technology Stack', 'Cost Forever', 'Built for Serious Forensics', 'Three Steps to a Verdict']) assert.ok(!html.includes(obsolete));
 }
}
console.log('UI checks passed: deployed media URLs, video timeline contract, scanner/history/privacy/terms render.');
`
const options = { loader: 'jsx', format: 'cjs', jsx: 'automatic', define: { 'import.meta.env.VITE_API_URL': JSON.stringify('https://api.example.test/api') } }
const originalJs = Module._extensions['.js']
function compileSource(module, filename) {
  module._compile(transformSync(readFileSync(filename, 'utf8'), options).code, filename)
}
Module._extensions['.jsx'] = compileSource
Module._extensions['.js'] = (module, filename) => filename.startsWith(resolve(root, 'src')) ? compileSource(module, filename) : originalJs(module, filename)
process.env.NODE_ENV = 'production'
const result = transformSync(code, options)
const compiled = new Module(resolve(root, 'verify-ui.cjs'))
compiled.filename = resolve(root, 'verify-ui.cjs')
compiled.paths = Module._nodeModulePaths(root)
compiled._compile(result.code, compiled.filename)
