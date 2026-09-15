/* Live UI acceptance: Program Coordinator -> Dean Academics programme approval. */
const { chromium } = require('playwright')

const baseUrl = process.env.ICMS_WEB_URL || 'http://127.0.0.1:8080'
const apiUrl = process.env.ICMS_API_URL || 'http://127.0.0.1:8010'

async function login(browser, username) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  page.setDefaultTimeout(10000)
  const response = await page.request.post(`${apiUrl}/api/auth/login`, { data: { username, password: 'demo123' } })
  if (!response.ok()) throw new Error(`${username} login failed: ${response.status()}`)
  const { token, user } = await response.json()
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
  await page.evaluate(({ token, user }) => { localStorage.setItem('icms_token', token); localStorage.setItem('icms_user', JSON.stringify(user)) }, { token, user })
  await page.reload({ waitUntil: 'domcontentloaded' })
  return { context, page, token }
}

;(async () => {
  const browser = await chromium.launch({ headless: true })
  const code = `DA-PROG-${Date.now().toString().slice(-7)}`
  let coordinator, dean
  try {
    coordinator = await login(browser, 'program_coordinator')
    await coordinator.page.getByText('Programme Requests', { exact: true }).click()
    await coordinator.page.getByText('New program proposal', { exact: true }).click()
    const form = coordinator.page.locator('.dean-proposal-form-modal')
    const inputs = form.locator('input')
    await inputs.nth(0).fill(code)
    await inputs.nth(1).fill(`Dean Live Programme ${code}`)
    await form.locator('select').nth(0).selectOption({ index: 1 })
    await form.locator('select').nth(1).selectOption({ index: 1 })
    await form.locator('textarea').fill(`Live source-to-Dean programme proposal ${code}`)
    await form.getByText('Save draft', { exact: true }).click()
    await coordinator.page.getByText(code, { exact: true }).waitFor()
    await coordinator.page.locator('.program-table-row').filter({ hasText: code }).getByText('Submit', { exact: true }).click()
    await coordinator.page.locator('.program-table-row').filter({ hasText: code }).getByText('SUBMITTED', { exact: true }).waitFor()

    const sourceList = await coordinator.page.request.get(`${apiUrl}/api/programs/proposals`, { headers: { Authorization: `Bearer ${coordinator.token}` } })
    const sourceData = await sourceList.json()
    const sourceProposal = sourceData.proposals.find(item => item.payload?.code === code)
    if (!sourceProposal || sourceProposal.state !== 'SUBMITTED' || !sourceProposal.events.some(e => e.to === 'SUBMITTED')) throw new Error('Source UI submission was not persisted with history')

    dean = await login(browser, 'dean_academics')
    const beforeDashboard = await (await dean.page.request.get(`${apiUrl}/api/academics/dean-dashboard`, { headers: { Authorization: `Bearer ${dean.token}` } })).json()
    await dean.page.getByText('Programs', { exact: true }).first().click()
    await dean.page.getByText(code, { exact: true }).waitFor()
    await dean.page.locator('.program-table-row').filter({ hasText: code }).getByText('Review', { exact: true }).click()
    const modal = dean.page.locator('.modal').filter({ hasText: code })
    const modalInputs = modal.locator('input')
    await modalInputs.nth(0).fill('40')
    await modalInputs.nth(1).fill('30')
    await modalInputs.nth(2).fill('4')
    await modal.getByLabel('Faculty confirmed').check()
    await modal.getByLabel('Infrastructure confirmed').check()
    await modal.getByText('Save feasibility assessment', { exact: true }).click()
    await modal.getByText('Approve', { exact: true }).click()
    await modal.waitFor({ state: 'hidden' })

    const deanList = await dean.page.request.get(`${apiUrl}/api/programs/proposals`, { headers: { Authorization: `Bearer ${dean.token}` } })
    const deanData = await deanList.json()
    const proposal = deanData.proposals.find(item => item.id === sourceProposal.id)
    if (!proposal || proposal.state !== 'APPROVED' || !proposal.implementation_ref || !proposal.events.some(e => e.to === 'APPROVED')) throw new Error('Dean UI approval did not create an approved programme implementation with history')
    const sourceAfter = await (await coordinator.page.request.get(`${apiUrl}/api/programs/proposals`, { headers: { Authorization: `Bearer ${coordinator.token}` } })).json()
    if (!sourceAfter.proposals.some(item => item.id === proposal.id && item.state === 'APPROVED')) throw new Error('Approved programme state did not propagate to source role')
    const afterDashboard = await (await dean.page.request.get(`${apiUrl}/api/academics/dean-dashboard`, { headers: { Authorization: `Bearer ${dean.token}` } })).json()
    if (Number(afterDashboard.kpis?.programs) !== Number(beforeDashboard.kpis?.programs) + 1) throw new Error('Dean programme KPI did not increase after implementation')
    console.log(`Dean programme live E2E passed: ${code} (${proposal.id})`)
  } finally {
    if (coordinator) await coordinator.context.close()
    if (dean) await dean.context.close()
    await browser.close()
  }
})().catch(error => { console.error(error); process.exitCode = 1 })
