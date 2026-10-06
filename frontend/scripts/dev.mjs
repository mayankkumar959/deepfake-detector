import { spawn, execFileSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { dirname, resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const project = resolve(frontend, '..')
const mode = process.argv[2] || '--both'
const requiredBackendFiles = [
  'app/main.py', 'app/config.py', 'app/database.py', 'app/models.py',
  'app/routers/__init__.py', 'app/routers/admin.py', 'app/routers/auth.py',
  'app/routers/dashboard.py', 'app/routers/health.py', 'app/routers/scans.py',
  'app/services/__init__.py', 'app/services/celery_app.py', 'app/services/detector.py',
  'app/services/face_utils.py', 'app/services/frame_analysis.py',
  'app/services/image_analysis.py', 'app/services/report.py',
  'app/services/retention.py', 'app/services/scan_access.py',
  'app/services/storage.py', 'app/services/video_analysis.py',
  'app/ml/general_image.py',
]
function findPython() {
  const missing = requiredBackendFiles.filter(file => !existsSync(join(project, 'backend', file)))
  if (missing.length) throw new Error(`Required backend files are missing. Restore them from Git before starting: ${missing.join(', ')}`)
  const candidates = [process.env.FORTEXA_PYTHON, join(project, '.venv', 'Scripts', 'python.exe'), join(project, '.venv', 'bin', 'python')]
  if (process.env.LOCALAPPDATA) {
    for (const parent of [join(process.env.LOCALAPPDATA, 'Python'), join(process.env.LOCALAPPDATA, 'Programs', 'Python')]) {
      if (existsSync(parent)) for (const name of readdirSync(parent)) candidates.push(join(parent, name, 'python.exe'))
    }
  }
  candidates.push('python', 'python3', 'py')
  for (const candidate of candidates.filter(Boolean)) {
    try {
      execFileSync(candidate, ['-c', 'import uvicorn,fastapi,cv2,sqlalchemy,pydantic_settings'], { stdio: 'ignore', windowsHide: true, timeout: 10000 })
      return candidate
    } catch { /* Try next interpreter. */ }
  }
  throw new Error('No Python with backend dependencies found. Set FORTEXA_PYTHON and install backend/requirements.txt and requirements-ml.txt.')
}
const children = []
let viteServer
let stopping = false
function stop(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) child.kill()
  if (viteServer?.close) viteServer.close().catch(error => console.error(error.message))
  else viteServer?.httpServer.close()
  process.exitCode = code
}
try {
  if (mode === '--check') {
    console.log(`Backend Python: ${findPython()}`)
    console.log('Startup dependency check passed.')
    process.exit(0)
  }
  if (mode !== '--web') {
    const python = findPython()
    console.log(`Backend Python: ${python}`)
    children.push(spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], {
      cwd: join(project, 'backend'), stdio: 'inherit', windowsHide: true,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    }))
  }
  if (mode !== '--api') {
    const { createServer, preview } = await import('vite')
    const { default: config } = await import('../vite.config.js')
    if (mode === '--serve') viteServer = await preview({ ...config, root: frontend, configFile: false })
    else {
      viteServer = await createServer({ ...config, root: frontend, configFile: false })
      await viteServer.listen()
    }
    viteServer.printUrls()
  }
  for (const child of children) {
    child.on('error', error => { console.error(error.message); stop(1) })
    child.on('exit', code => { if (!stopping) stop(code || 0) })
  }
  process.on('SIGINT', () => stop())
  process.on('SIGTERM', () => stop())
} catch (error) { console.error(error.message); stop(1) }
