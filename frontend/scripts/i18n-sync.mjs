import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, "..")
const localesDir = path.join(root, "src", "i18n", "locales")
const localeFiles = {
  en: path.join(localesDir, "en.json"),
  sn: path.join(localesDir, "sn.json"),
  nd: path.join(localesDir, "nd.json"),
}
const mode = process.argv.includes("--sync") ? "sync" : "check"

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"))
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`)
}

function flatten(value, prefix = "", output = {}) {
  for (const [key, entry] of Object.entries(value)) {
    const nextKey = prefix ? `${prefix}.${key}` : key
    if (entry && typeof entry === "object" && !Array.isArray(entry)) flatten(entry, nextKey, output)
    else output[nextKey] = entry
  }
  return output
}

function unflatten(flat) {
  const output = {}
  for (const [key, value] of Object.entries(flat)) {
    const parts = key.split(".")
    let current = output
    parts.forEach((part, index) => {
      if (index === parts.length - 1) current[part] = value
      else current = current[part] ||= {}
    })
  }
  return output
}

function usedTranslationKeys() {
  const srcDir = path.join(root, "src")
  const keys = new Set()
  const patterns = [
    /\bt\(\s*["'`]([^"'`]+)["'`]/g,
    /i18nKey=["']([^"']+)["']/g,
  ]

  function walk(dir) {
    for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, item.name)
      if (item.isDirectory()) {
        if (!["i18n"].includes(item.name)) walk(fullPath)
        continue
      }
      if (!/\.(ts|tsx|js|jsx)$/.test(item.name)) continue
      const content = fs.readFileSync(fullPath, "utf8")
      for (const pattern of patterns) {
        for (const match of content.matchAll(pattern)) keys.add(match[1])
      }
    }
  }

  walk(srcDir)
  return keys
}

const master = flatten(readJson(localeFiles.en))
const masterKeys = Object.keys(master).sort()
let hasProblems = false

for (const locale of ["sn", "nd"]) {
  const current = flatten(readJson(localeFiles[locale]))
  const missing = masterKeys.filter((key) => !(key in current))
  const extra = Object.keys(current).filter((key) => !(key in master)).sort()

  if (missing.length || extra.length) hasProblems = true

  if (missing.length) {
    console.log(`${locale}: missing ${missing.length} key(s)`)
    missing.forEach((key) => console.log(`  + ${key}`))
  }
  if (extra.length) {
    console.log(`${locale}: extra ${extra.length} key(s)`)
    extra.forEach((key) => console.log(`  - ${key}`))
  }

  if (mode === "sync" && missing.length) {
    for (const key of missing) current[key] = master[key]
    const ordered = {}
    for (const key of masterKeys) ordered[key] = current[key]
    for (const key of extra) ordered[key] = current[key]
    writeJson(localeFiles[locale], unflatten(ordered))
    console.log(`${locale}: synced missing keys from English fallback values.`)
  }
}

const usedKeys = usedTranslationKeys()
const unused = masterKeys.filter((key) => !usedKeys.has(key))
if (unused.length) {
  console.log(`en: ${unused.length} key(s) not referenced by static t("...") calls yet`)
  unused.forEach((key) => console.log(`  ? ${key}`))
}

if (hasProblems && mode !== "sync") {
  console.error("i18n check failed. Run npm run i18n:sync to add missing fallback keys.")
  process.exit(1)
}

console.log(`i18n ${mode} complete.`)
