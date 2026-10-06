// Run against npm run serve with a disposable database. Never use production data.
import { spawn } from 'node:child_process'
import { existsSync, mkdtempSync, writeFileSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'
const project = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const fixture = join(project, 'backend', '.runtime-check', 'blank.png')
let health
const readinessDeadline = Date.now() + 60000
while (!health && Date.now() < readinessDeadline) {
  try {
    const response = await fetch('http://localhost:5173/api/health', { signal: AbortSignal.timeout(3000) })
    if (response.ok) health = await response.json()
  } catch { /* Cold-start model loading can temporarily leave the API unavailable. */ }
  if (!health) await new Promise(resolve => setTimeout(resolve, 500))
}
assert.ok(health, 'API did not become ready within 60 seconds')
assert.equal(health.environment, 'test', 'Browser checks require an isolated APP_ENV=test backend; refusing to mutate normal user data.')
if (!existsSync(fixture)) throw new Error('Create backend/.runtime-check/blank.png before running this isolated browser check.')
const browser = [process.env.FORTEXA_BROWSER, 'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].filter(Boolean).find(existsSync)
if (!browser) throw new Error('Chrome or Edge is required')
const profile = mkdtempSync(join(tmpdir(), 'fortexa-browser-check-'))
const processHandle = spawn(browser, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-debugging-pipe', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] })
let browserErrors = ''
processHandle.stderr.on('data', chunk => { browserErrors = (browserErrors + chunk.toString()).slice(-4000) })
const sleep = ms => new Promise(r => setTimeout(r, ms))
let sessionId
let nextId = 1
const pending = new Map()
const badResponses = []
const browserExceptions = []
let downloadedReport
function command(method, params = {}) {
  return new Promise((resolveCommand, reject) => {
    const id = nextId++
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 15000)
    pending.set(id, { resolve: resolveCommand, reject, timer })
    processHandle.stdio[3].write(JSON.stringify({ id, method, params, ...(sessionId && !method.startsWith('Browser.') && !method.startsWith('Target.') ? { sessionId } : {}) }) + '\0')
  })
}
async function evaluate(expression) {
  const data = await command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (data.exceptionDetails) throw new Error(JSON.stringify(data.exceptionDetails))
  return data.result.value
}
async function waitFor(expression) {
  for (let i = 0; i < 100; i++) {
    try {
      if (await evaluate(`Boolean(document.body && (${expression}))`)) return
    } catch (error) {
      // Navigation replaces the execution context; retry only that transient case.
      if (!/Execution context was destroyed|Cannot find context/.test(error.message)) throw error
    }
    await sleep(200)
  }
  throw new Error(`Browser condition timed out: ${expression}`)
}
try {
  const receive = data => {
    if (data.id && pending.has(data.id)) {
      const request = pending.get(data.id)
      clearTimeout(request.timer)
      pending.delete(data.id)
      if (data.error) request.reject(new Error(data.error.message)); else request.resolve(data.result)
    }
    if (data.method === 'Network.responseReceived' && data.params.response.url.startsWith('http://localhost:5173') && data.params.response.status >= 400) badResponses.push(data.params.response.url)
    if (data.method === 'Page.javascriptDialogOpening') command('Page.handleJavaScriptDialog', { accept: true }).catch(() => {})
    if (data.method === 'Runtime.exceptionThrown') browserExceptions.push(data.params.exceptionDetails)
    if (data.method === 'Browser.downloadProgress' && data.params.state === 'completed') downloadedReport = data.params.guid
  }
  let buffer = ''
  processHandle.stdio[4].on('data', chunk => {
    buffer += chunk.toString()
    let end
    while ((end = buffer.indexOf('\0')) >= 0) {
      const packet = buffer.slice(0, end)
      buffer = buffer.slice(end + 1)
      if (packet) receive(JSON.parse(packet))
    }
  })
  const target = await command('Target.createTarget', { url: 'about:blank' })
  const attached = await command('Target.attachToTarget', { targetId: target.targetId, flatten: true })
  sessionId = attached.sessionId
  await command('Page.enable')
  await command('Runtime.enable')
  await command('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: join(profile, 'downloads'), eventsEnabled: true })
  await command('Network.enable')
  await command('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false })
  await command('Page.navigate', { url: 'http://localhost:5173/' })
  await waitFor("document.body.innerText.includes('Scan Your Media')")
  const document = await command('DOM.getDocument')
  const input = await command('DOM.querySelector', { nodeId: document.root.nodeId, selector: 'input[type=file]' })
  await command('DOM.setFileInputFiles', { nodeId: input.nodeId, files: [fixture] })
  await waitFor("Array.from(document.querySelectorAll('button')).some(b=>b.textContent.includes('Start Analysis'))")
  await evaluate("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Start Analysis')).click()")
  await waitFor("document.body.innerText.includes('Inconclusive Analysis')")
  await waitFor("Array.from(document.querySelectorAll('img')).filter(i=>i.src.includes('/api/scans/')).every(i=>i.complete&&i.naturalWidth>0)")
  assert.ok(await evaluate("document.body.innerText.includes('insufficient visual detail')"))
  console.log('Browser upload, polling, inconclusive result and protected media passed.')
  const reportPath = await evaluate("Array.from(document.querySelectorAll('a')).find(a=>a.textContent==='Full Report').href")
  await command('Page.navigate', { url: reportPath })
  await waitFor("document.body.innerText.includes('Scan Report')")
  assert.ok(await evaluate("document.body.innerText.includes('Download Report')"))
  await evaluate("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Download Report')).click()")
  for (let i = 0; i < 50 && !downloadedReport; i++) await sleep(100)
  assert.ok(downloadedReport, 'Report download did not complete')
  const { readdirSync } = await import('node:fs')
  const downloadedName = readdirSync(join(profile, 'downloads')).find(name => /^fortexa-.*\.json$/.test(name))
  assert.ok(downloadedName, 'Missing report JSON file')
  const report = JSON.parse(readFileSync(join(profile, 'downloads', downloadedName), 'utf8'))
  assert.ok(Array.isArray(report.warnings) && report.warnings.length > 0)
  console.log('Browser report JSON download passed.')
  await command('Page.navigate', { url: 'http://localhost:5173/history' })
  await waitFor("document.body.innerText.includes('blank.png')")
  await evaluate("document.querySelector('button[aria-label=\"Delete blank.png\"]').click()")
  await waitFor("document.body.innerText.includes('No scans yet')")
  // General real/AI integration fixtures; not an accuracy benchmark.
  for (const label of [0, 1]) {
    const imagePath = join(project, 'backend/data/general-ai-fixtures', label ? 'ai-0.jpg' : 'real-0.jpg')
    assert.ok(existsSync(imagePath), 'Missing general real/AI fixture')
    await command('Page.navigate', { url: 'http://localhost:5173/' })
    await waitFor("document.querySelector('input[type=file]')")
    const doc = await command('DOM.getDocument')
    const field = await command('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' })
    await command('DOM.setFileInputFiles', { nodeId: field.nodeId, files: [imagePath] })
    await waitFor("Array.from(document.querySelectorAll('button')).some(b=>b.textContent.includes('Start Analysis'))")
    await evaluate("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Start Analysis')).click()")
    await waitFor("document.body.innerText.includes('Analysis Result') && document.body.innerText.includes('Full Report')")
    assert.ok(await evaluate("!document.body.innerText.includes('Evaluation scope:')"), 'Technical warnings should be collapsed by default')
    assert.ok(await evaluate("document.body.innerText.includes('Results can be wrong')"), 'Essential reliability note must remain visible')
    await evaluate("document.querySelector('details summary').click()")
    assert.ok(await evaluate("document.body.innerText.includes('Evaluation scope:')"), 'Detailed limitations must remain accessible')
    await waitFor("Array.from(document.querySelectorAll('img')).filter(i=>i.src.includes('/api/scans/')).every(i=>i.complete&&i.naturalWidth>0)")
  }
  console.log('Browser general real and AI-generated image upload/render passed (integration, not accuracy benchmark).')
  for (const [route, title] of [['/privacy', 'Privacy Policy'], ['/terms', 'Terms of Service']]) {
    await command('Page.navigate', { url: `http://localhost:5173${route}` })
    await waitFor(`document.body.innerText.includes(${JSON.stringify(title)})`)
  }
  assert.deepEqual(badResponses, [])
  assert.deepEqual(browserExceptions, [], 'Uncaught browser application exception')
  await command('Page.navigate', { url: 'http://localhost:5173/' })
  await waitFor("document.body.innerText.includes('Scan Your Media')")
  assert.ok(await evaluate("!document.body.innerText.includes('Technology Stack') && !document.body.innerText.includes('Built for Serious Forensics')"), 'Redundant marketing sections should be absent')
  const screenshot = await command('Page.captureScreenshot', { format: 'png' })
  const output = join(project, 'backend', '.runtime-check', 'browser-scanner.png')
  writeFileSync(output, Buffer.from(screenshot.data, 'base64'))
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await sleep(300)
  assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Scanner overflows mobile viewport')
  const mobileScreenshot = await command('Page.captureScreenshot', { format: 'png' })
  writeFileSync(join(project, 'backend/.runtime-check/browser-scanner-mobile.png'), Buffer.from(mobileScreenshot.data, 'base64'))
  assert.ok(await evaluate("Array.from(document.querySelectorAll('a')).some(a=>a.textContent.includes('Your Scans') && a.getBoundingClientRect().width>0)"), 'Mobile history navigation is inaccessible')
  await command('Page.navigate', { url: 'http://localhost:5173/history' })
  await waitFor("document.body.innerText.includes('Your Scan History') && !document.body.innerText.includes('Loading scans')")
  assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'History overflows mobile viewport')
  console.log(`Browser report, private history and deletion passed. Screenshot: ${output}`)
  await command('Browser.close')
} finally {
  for (const request of pending.values()) clearTimeout(request.timer)
  processHandle.kill()
  if (browserErrors) console.error(browserErrors)
}
