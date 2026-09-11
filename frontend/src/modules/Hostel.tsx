import { useState, useEffect } from 'react'
import { api } from '../api'
import { Modal, PageHead, Spinner, DecisionToast, Kpis } from './kit'

type RequestRow = { id: string; student: string; status: string }
type Room = { id: string; block: string; room_no: string; capacity: number; occupied: number; vacant: number }

export default function Hostel({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [decision, setDecision] = useState<any>(null)
  const [request, setRequest] = useState<RequestRow | null>(null)
  const [rooms, setRooms] = useState<Room[]>([])
  const [roomsLoading, setRoomsLoading] = useState(false)
  const [roomsError, setRoomsError] = useState('')
  const [selectedRoom, setSelectedRoom] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function load() {
    setLoading(true); setError('')
    try { setData(await api.hostel()) }
    catch (e: any) { setError(e.message || 'Unable to load hostel allocation requests.') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function openAllocation(row: RequestRow) {
    setRequest(row); setRooms([]); setSelectedRoom(''); setRoomsError(''); setRoomsLoading(true)
    try { const result = await api.availableHostelRooms(row.id); setRooms(result.rooms || []) }
    catch (e: any) { setRoomsError(e.message || 'Unable to load available rooms.') }
    finally { setRoomsLoading(false) }
  }

  function closeAllocation() { if (!submitting) setRequest(null) }

  async function allocate() {
    if (!request || !selectedRoom) return
    setSubmitting(true)
    try {
      const result = await api.allocateHostel(request.id, selectedRoom)
      setRequest(null)
      setDecision({ ...result.decision, reason: `${result.decision?.reason || 'Room allocated.'} ${result.room.block} ${result.room.room_no}.` })
      await load()
    } catch (e: any) { setRoomsError(e.message || 'Unable to allocate the selected room.') }
    finally { setSubmitting(false) }
  }

  if (loading) return <Spinner />
  if (error || !data) return <div className="fade-in principal-hostel"><PageHead title="Hostel" sub="Occupancy and allocation requests" /><div className="hostel-error"><span>{error || 'Hostel information is currently unavailable.'}</span><button className="btn btn-sm btn-solid" onClick={load}>Retry</button></div></div>

  const s = data.summary
  const canAllocate = Boolean(data.can_allocate && caps.allocate)
  return (
    <div className="fade-in principal-hostel">
      <PageHead title="Hostel" sub="Campus occupancy and student room allocation requests" />
      <Kpis items={[
        { label: 'Rooms', value: s.rooms }, { label: 'Capacity', value: s.capacity },
        { label: 'Occupied', value: s.occupied }, { label: 'Vacant', value: s.vacant, tone: 'var(--teal)' },
      ]} />
      <div className="card principal-hostel-card" style={{ marginTop: 20 }}>
        <div className="card-h"><div><h3>Allocation requests</h3><p>Choose a vacant room to complete a pending request.</p></div></div>
        <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Student</th><th>Status</th><th style={{ textAlign: 'right' }}>Action</th></tr></thead><tbody>
          {data.requests.map((row: RequestRow) => <tr key={row.id}><td><b>{row.student}</b></td><td><span className={`pill s-${row.status}`}>{row.status}</span></td><td style={{ textAlign: 'right' }}><button className="btn btn-sm btn-teal" disabled={!canAllocate} title={canAllocate ? 'Select a room' : 'Your role is not authorized to allocate rooms'} onClick={() => openAllocation(row)}>Allocate room</button></td></tr>)}
          {data.requests.length === 0 && <tr><td colSpan={3}><div className="empty">No pending requests in your authorized campus</div></td></tr>}
        </tbody></table></div>
      </div>

      {request && <Modal title={`Allocate room — ${request.student}`} onClose={closeAllocation} className="principal-hostel-modal" footer={<><span>{selectedRoom ? 'Capacity is revalidated when you confirm.' : 'Select one available room.'}</span><button className="btn btn-sm" disabled={submitting} onClick={closeAllocation}>Cancel</button><button className="btn btn-sm btn-teal" disabled={!selectedRoom || submitting} onClick={allocate}>{submitting ? 'Allocating…' : 'Confirm allocation'}</button></>}>
        <p className="hostel-modal-note">Only rooms with current availability in your authorized campus are shown.</p>
        {roomsLoading && <div className="hostel-room-loading">Loading available rooms…</div>}
        {roomsError && <div className="hostel-modal-error"><span>{roomsError}</span><button className="btn btn-sm" disabled={submitting} onClick={() => openAllocation(request)}>Retry</button></div>}
        {!roomsLoading && !roomsError && rooms.length === 0 && <div className="empty">No rooms are currently available.</div>}
        {!roomsLoading && rooms.length > 0 && <div className="hostel-room-list" role="radiogroup" aria-label="Available rooms">{rooms.map(room => <label className={`hostel-room-option ${selectedRoom === room.id ? 'selected' : ''}`} key={room.id}><input type="radio" name="hostel-room" value={room.id} checked={selectedRoom === room.id} disabled={submitting} onChange={() => setSelectedRoom(room.id)} /><span><b>{room.block} · Room {room.room_no}</b><small>{room.vacant} of {room.capacity} bed{room.capacity === 1 ? '' : 's'} available</small></span></label>)}</div>}
      </Modal>}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
