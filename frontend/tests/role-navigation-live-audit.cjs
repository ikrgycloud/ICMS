/*
 * Non-mutating browser audit for the principal academic delivery roles.
 * It signs in through the visible UI and visits only read/navigation screens.
 * Run: ICMS_WEB_URL=http://127.0.0.1:8081 node tests/role-navigation-live-audit.cjs
 */
const { chromium } = require('playwright')

const baseUrl = process.env.ICMS_WEB_URL || 'http://127.0.0.1:8081'
const roles = [
  ['academic_coordinator', ['Overview', 'Academic Calendar', 'Course Offerings', 'Sections & Timetable', 'Faculty Allocation']],
  ['dean_academics', ['Overview', 'Academic Calendar', 'Faculty Allocation', 'Timetable Readiness', 'My Approvals']],
  ['vice_principal', ['Overview', 'Academic Calendar', 'Academic Approvals']],
  ['hod', ['Overview', 'Course Offerings', 'Sections & Timetable', 'Faculty Allocation']],
  ['principal', ['Principal', 'At-Risk Students', 'Academic Calendar', 'Faculty & Staff', 'Finance', 'My Approvals', 'Workflows']],
  ['professor', ['Overview', 'My Sections', 'Attendance', 'Assessments & Marks', 'My Requests']],
]
const selectedRole = process.argv[2]
const selectedScreen = process.env.ICMS_AUDIT_SCREEN
const auditedRoles = selectedRole ? roles.filter(([username]) => username === selectedRole) : roles
if (selectedRole && !auditedRoles.length) throw new Error(`Unknown audit role: ${selectedRole}`)

async function signIn(page, username) {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /sign in/i }).first().click()
  await page.locator('input[autocomplete="username"]').fill(username)
  await page.locator('input[autocomplete="current-password"]').fill('demo123')
  await page.locator('form').getByRole('button', { name: /sign in/i }).click()
  await page.locator('.nav-item').first().waitFor({ timeout: 30000 })
}

;(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' })
  const findings = []
  try {
    for (const [username, roleScreens] of auditedRoles) {
      const screens = selectedScreen ? roleScreens.filter(screen => screen === selectedScreen) : roleScreens
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
      const page = await context.newPage()
      const roleIssues = []
      page.on('pageerror', error => roleIssues.push(`browser error: ${error.message}`))
      page.on('response', response => {
        if (response.url().includes('/api/') && response.status() >= 400) {
          roleIssues.push(`HTTP ${response.status()}: ${new URL(response.url()).pathname}`)
        }
      })
      await signIn(page, username)
      for (const label of screens) {
        const item = page.locator('.nav-item').filter({ hasText: label }).first()
        if (!await item.count()) {
          roleIssues.push(`missing navigation item: ${label}`)
          continue
        }
        if (await item.evaluate(node => node.classList.contains('nav-item-disabled'))) {
          roleIssues.push(`disabled navigation item: ${label}`)
          continue
        }
        const started = Date.now()
        await item.click()
        await page.waitForTimeout(3500)
        const elapsed = Date.now() - started
        if (elapsed > 10000) roleIssues.push(`slow navigation (${elapsed}ms): ${label}`)
      }
      if (!await page.locator('#root').innerText()) roleIssues.push('application root rendered empty')
      if (roleIssues.length) findings.push({ username, issues: [...new Set(roleIssues)] })
      console.log(`${username}: ${roleIssues.length ? `${roleIssues.length} issue(s)` : 'navigation audit passed'}`)
      await context.close()
    }
  } finally {
    await browser.close()
  }
  if (findings.length) throw new Error(JSON.stringify(findings, null, 2))
  console.log('Role navigation audit passed')
})().catch(error => { console.error(error); process.exitCode = 1 })
