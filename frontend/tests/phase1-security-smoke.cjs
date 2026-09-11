const { chromium } = require('playwright')

const baseUrl = process.env.ICMS_WEB_URL || 'http://127.0.0.1:8080'

async function login(page, username) {
  await page.goto(baseUrl)
  await page.getByRole('button', { name: /sign in to your portal/i }).click()
  const user = page.locator('input[placeholder="e.g. student"]')
  const password = page.locator('input[type="password"]')
  await user.fill(username)
  await password.fill('demo123')
  await page.getByRole('button', { name: /sign in|login/i }).click()
  await page.waitForLoadState('networkidle')
}

;(async () => {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  await login(page, 'dean_academics')
  await page.getByText('Dean Academics Command Centre').waitFor({ state: 'visible', timeout: 15000 })
  if (!(await page.getByText('Timetable exceptions').count())) throw new Error('Dean dashboard did not render')
  await browser.close()
  console.log('phase1 browser smoke passed')
})().catch(error => {
  console.error(error)
  process.exitCode = 1
})
