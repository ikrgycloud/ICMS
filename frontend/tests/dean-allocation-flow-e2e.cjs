/* Live UI acceptance: HoD -> Dean Academics faculty allocation. */
const { chromium } = require('playwright')
const web = process.env.ICMS_WEB_URL || 'http://127.0.0.1:8080'
const api = process.env.ICMS_API_URL || 'http://127.0.0.1:8010'
async function login(browser, username) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage(); page.setDefaultTimeout(10000)
  const response = await page.request.post(`${api}/api/auth/login`, { data: { username, password: 'demo123' } })
  if (!response.ok()) throw new Error(`${username} login failed: ${response.status()}`)
  const { token, user } = await response.json()
  await page.goto(web, { waitUntil: 'domcontentloaded' })
  await page.evaluate(({ token, user }) => { localStorage.icms_token = token; localStorage.icms_user = JSON.stringify(user) }, { token, user })
  await page.reload({ waitUntil: 'domcontentloaded' })
  return { context, page, token }
}
;(async () => {
  const browser = await chromium.launch({ headless: true })
  let hod, dean
  try {
    hod = await login(browser, 'hod')
    await hod.page.getByRole('button', { name: 'Academics', exact: true }).click()
    await hod.page.getByText('Faculty allocation', { exact: true }).click()
    await hod.page.getByText('Propose allocation', { exact: true }).waitFor()
    const initial = await (await hod.page.request.get(`${api}/api/academics/allocation/proposals`, { headers: { Authorization: `Bearer ${hod.token}` } })).json()
    await hod.page.getByText('Propose allocation', { exact: true }).click()
    const modal = hod.page.locator('.modal').filter({ hasText: 'Propose Faculty Allocation' })
    const selects = modal.locator('select')
    const sectionId = await selects.nth(0).inputValue()
    const facultyId = await selects.nth(1).inputValue()
    await modal.getByText('Save', { exact: true }).click()
    await modal.waitFor({ state: 'hidden' })
    const source = await (await hod.page.request.get(`${api}/api/academics/allocation/proposals`, { headers: { Authorization: `Bearer ${hod.token}` } })).json()
    const proposal = source.proposals.find(p => !initial.proposals.some(before => before.id === p.id) && p.state === 'SUBMITTED')
    if (!proposal || !proposal.events.some(e => e.to === 'SUBMITTED')) throw new Error('HoD allocation UI did not persist a submitted proposal with history')
    dean = await login(browser, 'dean_academics')
    const before = await (await dean.page.request.get(`${api}/api/academics/dean-dashboard`, { headers: { Authorization: `Bearer ${dean.token}` } })).json()
    await dean.page.getByText('Faculty Allocation', { exact: true }).first().click()
    await dean.page.getByText(proposal.title, { exact: true }).waitFor()
    await dean.page.locator('.dean-workspace-row').filter({ hasText: proposal.title }).getByText('Approve', { exact: true }).click()
    await dean.page.locator('.dean-workspace-row').filter({ hasText: proposal.title }).getByText('APPROVED', { exact: true }).waitFor()
    const finalSource = await (await hod.page.request.get(`${api}/api/academics/allocation/proposals`, { headers: { Authorization: `Bearer ${hod.token}` } })).json()
    const final = finalSource.proposals.find(p => p.id === proposal.id)
    if (!final || final.state !== 'APPROVED' || !final.implementation_ref || !final.events.some(e => e.to === 'APPROVED')) throw new Error('Dean approval did not propagate allocation state/implementation/history')
    const notifications = await dean.page.request.get(`${api}/api/notifications`, { headers: { Authorization: `Bearer ${dean.token}` } })
    const notices = await notifications.json()
    if (!notices.notifications.some(n => String(n.body || '').includes(proposal.title))) throw new Error('Dean allocation notification missing')
    const after = await (await dean.page.request.get(`${api}/api/academics/dean-dashboard`, { headers: { Authorization: `Bearer ${dean.token}` } })).json()
    if (Number(after.approvals?.allocation || 0) !== Number(before.approvals?.allocation || 0) - 1) throw new Error('Dean allocation pending KPI did not decrease after approval')
    console.log(`Dean allocation live E2E passed: ${proposal.id}; section=${sectionId}; faculty=${facultyId}`)
  } finally { if (hod) await hod.context.close(); if (dean) await dean.context.close(); await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
