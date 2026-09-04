import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Modal, GatedBtn } from './kit'

export default function Library({ caps }: { caps: any }) {
  const [tab, setTab] = useState<'catalog' | 'loans'>('catalog')
  const [books, setBooks] = useState<any>(null)
  const [loans, setLoans] = useState<any>(null)
  const [q, setQ] = useState('')
  const [decision, setDecision] = useState<any>(null)
  const [issue, setIssue] = useState<any>(null)
  const [borrower, setBorrower] = useState('')

  function load() {
    api.books(q).then(setBooks).catch(() => {})
    api.loans().then(setLoans).catch(() => {})
  }
  useEffect(() => { load() }, [])

  async function doIssue() {
    try {
      const r = await api.issueBook({ book_id: issue.id, borrower, borrower_name: borrower })
      setDecision(r.decision); setIssue(null); setBorrower(''); load()
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }); setIssue(null) }
  }
  async function ret(id: string) {
    try { const r = await api.returnBook(id); setDecision(r.decision); load() }
    catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  if (!books) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Library" sub="Catalogue and circulation" />
      <div className="tabs">
        <button className={`tab ${tab === 'catalog' ? 'on' : ''}`} onClick={() => setTab('catalog')}>Catalogue</button>
        <button className={`tab ${tab === 'loans' ? 'on' : ''}`} onClick={() => setTab('loans')}>Active loans ({loans?.loans.length || 0})</button>
      </div>

      {tab === 'catalog' && (
        <>
          <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
            <input className="inp" style={{ maxWidth: 320 }} placeholder="Search title or author…" value={q}
              onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} />
            <button className="btn btn-out" onClick={load}>Search</button>
          </div>
          <div className="card">
            <div className="tbl-scroll">
              <table className="tbl">
                <thead><tr><th>Title</th><th>Author</th><th>Category</th><th>Available</th><th style={{ textAlign: 'right' }}></th></tr></thead>
                <tbody>
                  {books.books.map((b: any) => (
                    <tr key={b.id}>
                      <td><b>{b.title}</b></td>
                      <td>{b.author}</td>
                      <td><span className="tag">{b.category}</span></td>
                      <td><b style={{ color: b.available > 0 ? 'var(--teal)' : 'var(--rose)' }}>{b.available}</b> / {b.total}</td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-sm btn-brass" disabled={!caps.issue || b.available < 1} onClick={() => setIssue(b)}>Issue</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === 'loans' && loans && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Book</th><th>Borrower</th><th>Issued</th><th>Due</th><th></th></tr></thead>
              <tbody>
                {loans.loans.map((l: any) => (
                  <tr key={l.id}>
                    <td><b>{l.book}</b></td>
                    <td>{l.borrower}</td>
                    <td>{l.issued_on}</td>
                    <td>{l.overdue ? <span className="pill s-overdue">overdue</span> : l.due_on}</td>
                    <td style={{ textAlign: 'right' }}><button className="btn btn-sm btn-out" disabled={!caps.return} onClick={() => ret(l.id)}>Return</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {issue && (
        <Modal title={`Issue: ${issue.title}`} onClose={() => setIssue(null)}
          footer={<><button className="btn btn-out" onClick={() => setIssue(null)}>Cancel</button>
            <button className="btn btn-brass" onClick={doIssue} disabled={!borrower}>Issue book</button></>}>
          <div className="form-row"><label>Borrower (roll no / name)</label>
            <input className="inp" value={borrower} onChange={e => setBorrower(e.target.value)} /></div>
          <p className="hint">Due date is set to 14 days from today.</p>
        </Modal>
      )}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
