import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, PageHead, Spinner, money } from './kit'

export default function AccountantReport() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.allSettled([
      api.invoices(),
      api.financeReconciliations(),
      api.financeRefunds(),
      api.vendorPayments(),
      api.dayCloses(),
      api.payrollRuns(),
    ]).then(results => {
      if (!active) return
      const value = (index: number, key: string) => results[index].status === 'fulfilled' ? (results[index].value as any)?.[key] || [] : []
      const invoices = results[0].status === 'fulfilled' ? (results[0].value as any) : { summary: {}, invoices: [], payments: [] }
      setData({
        summary: invoices.summary || {},
        invoices: invoices.invoices || [],
        payments: invoices.payments || [],
        reconciliations: value(1, 'reconciliations'),
        refunds: value(2, 'refunds'),
        vendorPayments: value(3, 'vendor_payments'),
        dayCloses: value(4, 'day_closes'),
        payrollRuns: value(5, 'runs'),
      })
    }).catch(e => { if (active) setError(e.message || 'Unable to load accountant report') })
    return () => { active = false }
  }, [])

  if (error) return <div className="card card-pad calendar-banner warn">{error}</div>
  if (!data) return <Spinner />

  const summary = data.summary || {}
  const pendingInvoices = data.invoices.filter((row: any) => Number(row.balance || 0) > 0)
  const pendingPayments = data.payments.filter((row: any) => ['pending_clearance', 'pending_verification'].includes(row.status))
  const approvedRefunds = data.refunds.filter((row: any) => row.status === 'approved')
  const dueVendors = data.vendorPayments.filter((row: any) => ['pending_approval', 'approved'].includes(row.status))
  const totalRefunds = data.refunds.reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0)
  const totalVendorDue = dueVendors.reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0)
  const totalBilled = Number(summary.total_billed || data.invoices.reduce((sum: number, row: any) => sum + Number(row.amount || row.total_amount || 0), 0))
  const totalCollected = Number(summary.total_collected || data.payments.filter((row: any) => ['paid', 'cleared', 'approved', 'collected'].includes(String(row.status || '').toLowerCase())).reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0))
  const outstanding = Number(summary.outstanding || Math.max(0, totalBilled - totalCollected))

  const collectionMix = [
    { label: 'Collected', value: Math.max(0, totalCollected), color: '#0d9d6a' },
    { label: 'Outstanding', value: Math.max(0, outstanding), color: '#f5a623' },
    { label: 'Refunded', value: Math.max(0, totalRefunds), color: '#a64dcb' },
  ]
  const invoiceMix = [
    { label: 'Paid', value: data.invoices.filter((row: any) => String(row.status || '').toLowerCase() === 'paid').reduce((sum: number, row: any) => sum + Number(row.amount || row.total_amount || 0), 0), color: '#0d9d6a' },
    { label: 'Open', value: pendingInvoices.reduce((sum: number, row: any) => sum + Number(row.balance || row.amount || 0), 0), color: '#f0873a' },
    { label: 'Paid later', value: Math.max(0, totalBilled - totalCollected - outstanding), color: '#4b86ff' },
  ].filter(item => item.value > 0)

  const paymentFlow = [
    { label: 'Clearance', value: pendingPayments.length, color: '#2d8cff' },
    { label: 'Vendor due', value: dueVendors.length, color: '#f2a93b' },
    { label: 'Payroll', value: data.payrollRuns.length, color: '#1bb08a' },
  ]

  return <div className="fade-in accountant-report">
    <PageHead title="Accountant report" sub="Live finance, collections, controls, payroll, and outstanding action totals." />
    <div className="accountant-report-toolbar"><span>Database report</span><small>Generated from current ICMS records</small></div>
    <section className="accountant-report-kpis">
      <article><span>Total billed</span><b>{money(totalBilled)}</b></article>
      <article><span>Total collected</span><b>{money(totalCollected)}</b></article>
      <article><span>Outstanding fees</span><b>{money(outstanding)}</b></article>
      <article><span>Open invoices</span><b>{pendingInvoices.length}</b></article>
      <article><span>Pending payments</span><b>{pendingPayments.length}</b></article>
      <article><span>Payroll runs</span><b>{data.payrollRuns.length}</b></article>
    </section>

    <section className="accountant-report-visuals">
      <div className="card accountant-report-chart-card">
        <div className="card-h"><h3>Collection mix</h3></div>
        <div className="accountant-chart-box">
          <DonutChart items={collectionMix} total={Math.max(1, collectionMix.reduce((sum, item) => sum + item.value, 0))} title="Cash flow" />
          <ul className="accountant-legend">
            {collectionMix.map(item => <li key={item.label}><span className="dot" style={{ background: item.color }} />{item.label}<b>{money(item.value)}</b></li>)}
          </ul>
        </div>
      </div>

      <div className="card accountant-report-chart-card">
        <div className="card-h"><h3>Invoice status</h3></div>
        <div className="accountant-chart-box">
          <DonutChart items={invoiceMix} total={Math.max(1, invoiceMix.reduce((sum, item) => sum + item.value, 0))} title="Invoice mix" />
          <ul className="accountant-legend">
            {invoiceMix.map(item => <li key={item.label}><span className="dot" style={{ background: item.color }} />{item.label}<b>{money(item.value)}</b></li>)}
          </ul>
        </div>
      </div>

      <div className="card accountant-report-chart-card wide">
        <div className="card-h"><h3>Finance flow summary</h3></div>
        <div className="accountant-flow-bars">
          {paymentFlow.map(item => (
            <div key={item.label} className="accountant-flow-bar-wrap">
              <div className="accountant-flow-meta"><span>{item.label}</span><b>{item.value}</b></div>
              <div className="accountant-flow-track"><i style={{ width: `${Math.min(100, item.value * 10)}%`, background: item.color }} /></div>
            </div>
          ))}
        </div>
      </div>
    </section>

    <div className="accountant-report-grid">
      <ReportTable title="Reconciliation controls" columns={['Period', 'Collected', 'Closing', 'Status']} rows={data.reconciliations.slice(0, 8).map((row: any) => [String(row.period_end || '').slice(0, 10) || '—', money(row.total_collected), money(row.closing_balance), row.status])} empty="No reconciliation records yet." />
      <ReportTable title="Pending payment action" columns={['Reference', 'Method', 'Amount', 'Status']} rows={pendingPayments.slice(0, 8).map((row: any) => [row.reference || '—', row.method || '—', money(row.amount), row.status])} empty="No pending payment verification." />
      <ReportTable title="Refund exposure" columns={['Invoice', 'Amount', 'Status', 'Reason']} rows={data.refunds.slice(0, 8).map((row: any) => [String(row.invoice_id || '').slice(0, 12), money(row.amount), row.status, row.reason || '—'])} empty="No refund requests." footer={`${approvedRefunds.length} approved · ${money(totalRefunds)} total requested`} />
      <ReportTable title="Vendor payment exposure" columns={['Vendor', 'Amount', 'Status', 'Reference']} rows={data.vendorPayments.slice(0, 8).map((row: any) => [row.vendor_name || '—', money(row.amount), row.status, row.invoice_ref || '—'])} empty="No vendor payment records." footer={`${dueVendors.length} due · ${money(totalVendorDue)} outstanding`} />
    </div>
    <div className="accountant-report-footer"><b>{data.dayCloses.length}</b><span>day closes recorded</span><b>{data.payrollRuns.length}</b><span>payroll runs available</span><b>{data.invoices.length}</b><span>invoice rows loaded</span></div>
  </div>
}

function DonutChart({ items, total, title }: { items: { label: string; value: number; color: string }[]; total: number; title: string }) {
  const radius = 54
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return <div className="accountant-donut-shell">
    <svg viewBox="0 0 180 180" className="accountant-donut" role="img" aria-label={title}>
      <circle cx="90" cy="90" r={radius} fill="none" stroke="#edf2f8" strokeWidth="20" />
      {items.map(item => {
        const slice = total ? (item.value / total) * circumference : 0
        const dash = `${slice} ${circumference - slice}`
        const circle = <circle key={item.label} cx="90" cy="90" r={radius} fill="none" stroke={item.color} strokeWidth="20" strokeDasharray={dash} strokeDashoffset={-offset} strokeLinecap="round" transform="rotate(-90 90 90)" />
        offset += slice
        return circle
      })}
    </svg>
    <div className="accountant-donut-center"><b>{money(total)}</b><span>{title}</span></div>
  </div>
}

function ReportTable({ title, columns, rows, empty, footer }: { title: string; columns: string[]; rows: string[][]; empty: string; footer?: string }) {
  return <section className="card accountant-report-table"><div className="card-h"><h3>{title}</h3></div>{rows.length ? <div className="tbl-scroll"><table className="tbl"><thead><tr>{columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div> : <Empty text={empty} />}{footer && <footer>{footer}</footer>}</section>
}
