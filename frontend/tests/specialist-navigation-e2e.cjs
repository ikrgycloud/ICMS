const assert = require('node:assert/strict')
const { chromium } = require('playwright')

const baseUrl = process.env.ICMS_WEB_URL || 'http://127.0.0.1:8080'

;(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' })
  try {
    for (const [username, route, title] of [
      ['hr_manager', 'hr', 'HR Staffing Requests'],
      ['purchase', 'procurement', 'Procurement Requisitions'],
      ['maintenance', 'assets', 'Facilities Work Orders'],
      ['it_manager', 'assets', 'IT Service Requests'],
    ]) {
      const page = await browser.newPage()
      const errors = []
      page.on('pageerror', error => errors.push(error.message))
      const response = await page.request.post(`${baseUrl}/api/auth/login`, {
        data: { username, password: 'demo123' },
      })
      assert.equal(response.status(), 200)
      const { token, user } = await response.json()
      await page.goto(baseUrl)
      await page.evaluate(({ token, user }) => {
        localStorage.setItem('icms_token', token)
        localStorage.setItem('icms_user', JSON.stringify(user))
      }, { token, user })
      await page.goto(`${baseUrl}/#${route}`)
      await page.reload({ waitUntil: 'networkidle' })
      await page.getByRole('heading', { name: title, exact: true }).waitFor()
      await page.locator('.nav-item').filter({ hasText: 'Overview' }).first().click()
      await page.waitForFunction(() => location.hash === '#overview')
      await page.waitForLoadState('networkidle')
      assert.ok(await page.locator('#root').innerText(), 'Application must remain rendered')
      assert.deepEqual(errors, [], `${username}: unexpected browser errors`)
      await page.close()
      console.log(`${username}: specialist screen loads and unmounts without errors`)
    }
  } finally {
    await browser.close()
  }
})().catch(error => { console.error(error); process.exitCode = 1 })
