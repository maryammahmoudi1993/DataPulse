const { chromium } = require('playwright')
const path         = require('path')
const fs           = require('fs')

const BASE    = process.env.BASE_URL || 'http://localhost:3000'
const OUT_DIR = path.join(__dirname, 'output')
const DEMO    = { username: 'demo', password: 'demodemo1' }

const openSettings = page => page.click('button:has-text("Settings")')

const SHOTS = [
  {
    name: '01_dashboard',
    url:  '/',
    desc: 'Live dashboard with real-time chart and alert feed',
    wait: 4000,
  },
  {
    name: '02_alert_feed',
    url:  '/',
    desc: 'Alert feed showing severity badges (HIGH / CRITICAL)',
    wait: 6000,
    clip: { x: 0, y: 300, width: 1280, height: 500 },
  },
  {
    name: '03_simulator_controls',
    url:  '/',
    desc: 'Simulator controls — amplitude, noise, spike probability sliders',
    wait: 2000,
    clip: { x: 850, y: 280, width: 420, height: 360 },
  },
  {
    name: '04_workspace_members',
    url:  '/',
    desc: 'Workspace settings — Members tab',
    wait: 1000,
    action: async page => {
      await openSettings(page)
      await page.waitForSelector('text=Members')
    },
  },
  {
    name: '05_audit_log',
    url:  '/',
    desc: 'Workspace settings — Audit log tab',
    wait: 1000,
    action: async page => {
      await openSettings(page)
      await page.click('button:has-text("Audit log")')
      await page.waitForTimeout(800)
    },
  },
  {
    name: '06_integrations',
    url:  '/',
    desc: 'Workspace settings — Integrations tab (Slack + PagerDuty)',
    wait: 1000,
    action: async page => {
      await openSettings(page)
      await page.click('button:has-text("Integrations")')
      await page.waitForTimeout(800)
    },
  },
  {
    name: '07_swagger_ui',
    url:  '/api/schema/swagger-ui/',
    base: process.env.API_URL || 'http://localhost:8000',
    desc: 'Interactive API documentation — Swagger UI',
    wait: 2000,
  },
]

async function login(page) {
  await page.goto(`${BASE}/`)
  await page.waitForSelector('input[placeholder="Username"]')
  await page.fill('input[placeholder="Username"]', DEMO.username)
  await page.fill('input[placeholder="Password"]', DEMO.password)
  await page.click('button[type="submit"]')
  await page.waitForSelector('button:has-text("Settings")', { timeout: 15000 })
}

;(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true })

  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  })
  const page = await context.newPage()

  console.log('Logging in as demo user…')
  await login(page)

  for (const shot of SHOTS) {
    const shotBase = shot.base ?? BASE
    await page.goto(`${shotBase}${shot.url}`)
    await page.waitForTimeout(shot.wait ?? 2000)

    if (shot.action) {
      await shot.action(page)
    }

    const file = path.join(OUT_DIR, `${shot.name}.png`)
    if (shot.clip) {
      await page.screenshot({ path: file, clip: shot.clip })
    } else {
      await page.screenshot({ path: file, fullPage: false })
    }

    console.log(`✓ ${shot.name}.png — ${shot.desc}`)
  }

  await browser.close()
  console.log(`\nAll screenshots saved to ${OUT_DIR}`)
})()
