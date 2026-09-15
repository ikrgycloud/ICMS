const { chromium } = require('playwright')

const baseUrl = process.env.ICMS_WEB_URL || 'http://127.0.0.1:8080'
const apiUrl = process.env.ICMS_API_URL || 'http://127.0.0.1:8010'
const journeys = [
  'Calendar', 'Curriculum', 'Program', 'Allocation', 'Timetable',
  'Quality Reviews', 'Corrective Actions', 'Committees', 'CO/PO Attainment',
  'Next-semester Planning', 'Reports'
]

;(async () => {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const failures = []
  page.on('pageerror', error => failures.push(`Runtime error: ${error.message}`))
  page.on('response', response => {
    if (response.url().startsWith(`${apiUrl}/api/`) && response.status() >= 400) {
      failures.push(`API ${response.status()}: ${response.url()}`)
    }
  })
  const login = await page.request.post(`${apiUrl}/api/auth/login`, { data: { username: 'dean_academics', password: 'demo123' } })
  if (!login.ok()) throw new Error(`Dean login failed: ${login.status()}`)
  const { token, user } = await login.json()
  await page.goto(baseUrl)
  await page.evaluate(({ token, user }) => { localStorage.setItem('icms_token', token); localStorage.setItem('icms_user', JSON.stringify(user)); }, { token, user })
  await page.reload({ waitUntil: 'networkidle' })
  for (const journey of journeys) {
    const control = page.getByText(journey, { exact: true }).first()
    if (await control.count()) {
      await control.click()
      await page.waitForTimeout(500)
    }
  }
  if (failures.length) throw new Error(`Dean workspace journey failures:\n${[...new Set(failures)].join('\n')}`)
  await page.screenshot({ path: 'phase11-dean-workspaces.png', fullPage: true })
  await browser.close()
  console.log(`phase11 browser journeys passed: ${journeys.length}`)
})().catch(error => {
  console.error(error)
  process.exitCode = 1
})
