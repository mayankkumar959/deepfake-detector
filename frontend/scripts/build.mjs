import { build } from 'vite'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import config from '../vite.config.js'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
await build({ ...config, root, configFile: false })
