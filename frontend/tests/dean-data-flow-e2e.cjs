/*
 * Live acceptance test: an HoD creates a governed curriculum change through
 * the browser; Dean Academics sees and approves the same record through the
 * browser; the API then proves persistence, notification, and history.
 */
const { chromium } = require('playwright')

const baseUrl = process.env.ICMS_WEB_URL || 'http://127.0.0.1:8080'
const apiUrl = process.env.ICMS_API_URL || 'http://127.0.0.1:8010'

async function login(browser, username) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const response = await page.request.post(`${apiUrl}/api/auth/login`, { data: { username, password: 'demo123' } })
  if (!response.ok()) throw new Error(`${username} login failed: ${response.status()}`)
  const { token, user } = await response.json()
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
  await page.evaluate(({ token, user }) => {
    localStorage.setItem('icms_token', token)
    localStorage.setItem('icms_user', JSON.stringify(user))
  }, { token, user })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.locator('body').waitFor()
  return { context, page, token }
}

;(async () => {
  const browser = await chromium.launch({ headless: true })
  const code = `DAUD${Date.now().toString().slice(-8)}`
  let hod, dean
  try {
    dean = await login(browser, 'dean_academics')
    const beforeDashboardResponse = await dean.page.request.get(`${apiUrl}/api/academics/dean-dashboard`, { headers: { Authorization: `Bearer ${dean.token}` } })
    if (!beforeDashboardResponse.ok()) throw new Error(`Dean dashboard failed: ${beforeDashboardResponse.status()}`)
    const beforeDashboard = await beforeDashboardResponse.json()

    hod = await login(browser, 'hod')
    await hod.page.getByText('Curriculum', { exact: true }).first().click()
    await hod.page.getByText('New proposal', { exact: true }).click()
    const form = hod.page.locator('.curriculum-proposal-form-modal')
    const fields = form.locator('input')
    await fields.nth(0).fill(code)
    await fields.nth(1).fill('Dean live data-flow regression course')
    await form.locator('select').nth(0).selectOption('CSE')
    await fields.nth(2).fill('2026-Odd')
    await fields.nth(3).fill('3')
    await fields.nth(4).fill('1')
    await form.locator('textarea').fill(`DEAN-AUDIT: ${code} source-to-Dean approval`)
    await form.getByText('Submit for approval', { exact: true }).click()
    await hod.page.getByText(code, { exact: true }).waitFor()

    const pendingDashboardResponse = await dean.page.request.get(`${apiUrl}/api/academics/dean-dashboard`, { headers: { Authorization: `Bearer ${dean.token}` } })
    const pendingDashboard = await pendingDashboardResponse.json()
    if (Number(pendingDashboard.kpis.curriculum_reviews) !== Number(beforeDashboard.kpis.curriculum_reviews) + 1) {
      throw new Error('Dean curriculum-review KPI did not increase by one after the HoD submission')
    }

    await dean.page.getByText('Curriculum', { exact: true }).first().click()
    await dean.page.getByText(code, { exact: true }).waitFor()
    await dean.page.getByRole('button', { name: new RegExp(`^${code}\\s`) }).click()
    await dean.page.locator('.curriculum-review-modal').getByText('Approve', { exact: true }).click()
    await dean.page.locator('.curriculum-review-modal').waitFor({ state: 'hidden' })

    const proposals = await dean.page.request.get(`${apiUrl}/api/curriculum/proposals`, { headers: { Authorization: `Bearer ${dean.token}` } })
    const payload = await proposals.json()
    const proposal = payload.proposals.find((item) => item.payload && item.payload.code === code)
    if (!proposal || proposal.state !== 'APPROVED' || !proposal.implementation_ref) throw new Error('Approved proposal was not persisted')
    if (!proposal.events.some((event) => event.to === 'SUBMITTED') || !proposal.events.some((event) => event.to === 'APPROVED')) throw new Error('Proposal history is incomplete')

    const approvedDashboardResponse = await dean.page.request.get(`${apiUrl}/api/academics/dean-dashboard`, { headers: { Authorization: `Bearer ${dean.token}` } })
    const approvedDashboard = await approvedDashboardResponse.json()
    if (Number(approvedDashboard.kpis.curriculum_reviews) !== Number(beforeDashboard.kpis.curriculum_reviews)) {
      throw new Error('Dean curriculum-review KPI did not return to its baseline after approval')
    }
    if (Number(approvedDashboard.kpis.courses) !== Number(beforeDashboard.kpis.courses) + 1) {
      throw new Error('Dean course KPI did not increase after approved curriculum implementation')
    }

    const notifications = await dean.page.request.get(`${apiUrl}/api/notifications`, { headers: { Authorization: `Bearer ${dean.token}` } })
    const notificationPayload = await notifications.json()
    if (!notificationPayload.notifications.some((item) => String(item.body || '').includes(code))) throw new Error('Dean notification is missing')
    console.log(`Dean live data-flow E2E passed: ${code} (${proposal.id})`)
  } finally {
    if (hod) await hod.context.close()
    if (dean) await dean.context.close()
    await browser.close()
  }
})().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
