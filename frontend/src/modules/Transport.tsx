import { useEffect, useState } from 'react'
import { api, getUser } from '../api'
import { Empty, Kpis, PageHead, Pill, Spinner } from './kit'
import { FiCalendar, FiChevronDown, FiChevronUp, FiEdit2, FiFilter, FiMapPin, FiPlus, FiSearch, FiTrash2, FiUser, FiUsers, FiX, FiPhone, FiClock, FiSend, FiCheckCircle, FiRadio, FiNavigation } from 'react-icons/fi'
import { FaBus } from 'react-icons/fa'
import './student-transport.css'
import './student-transport-assigned.css'

type Tab = 'dashboard' | 'requests' | 'routes' | 'vehicles' | 'drivers' | 'students' | 'allocations'
type ModalType = 'driver' | 'vehicle' | 'route' | 'stop' | 'student-assign' | 'student-details' | 'request' | null

interface FormState {
  name: string
  route_code: string
  vehicle_number: string
  vehicle_type: string
  capacity: number | string
  employee_id: string
  phone: string
  license_number: string
  license_expiry: string
  vehicle_id: string
  status: string
  route_id: string
  stop_name: string
  stop_address: string
  pickup_time: string
  drop_time: string
  sequence: number | string
  student_id: string
  pickup_stop_id: string
  drop_stop_id: string
  driver_id: string
  start_date: string
  end_date: string
}

const emptyForm: FormState = {
  name: '',
  route_code: '',
  vehicle_number: '',
  vehicle_type: 'BUS',
  capacity: 40,
  employee_id: '',
  phone: '',
  license_number: '',
  license_expiry: '',
  vehicle_id: '',
  status: 'ACTIVE',
  route_id: '',
  stop_name: '',
  stop_address: '',
  pickup_time: '',
  drop_time: '',
  sequence: 1,
  student_id: '',
  pickup_stop_id: '',
  drop_stop_id: '',
  driver_id: '',
  start_date: new Date().toISOString().split('T')[0],
  end_date: '',
}

export default function Transport({ caps }: { caps: any }) {
  const user = getUser() || {}
  const isDriver = Number(user.office_n) === 31 && String(user.role || '').toLowerCase().includes('driver')

  if (['student', 'parent'].includes(String(user.persona || '').toLowerCase())) return <StudentTransport />
  return isDriver ? <DriverDashboard /> : <TransportManager />
}

export function TransportOverview({ caps, go }: { caps: any; go?: (view: string) => void }) {
  const [data, setData] = useState({ routes: [], vehicles: [], drivers: [], requests: [], allocations: [] })
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const [r, v, dr, q, a] = await Promise.all([
          api.transportRoutes(),
          api.transportVehicles(),
          api.transportDrivers(),
          api.transportRequests(),
          api.transportAllocations(),
        ])
        setData({
          routes: r.routes || [],
          vehicles: v.vehicles || [],
          drivers: dr.drivers || [],
          requests: q.requests || [],
          allocations: a.allocations || [],
        })
      } catch (error) {
        setData({ routes: [], vehicles: [], drivers: [], requests: [], allocations: [] })
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const visibleRoutes = data.routes.filter((route: any) => {
    const text = search.trim().toLowerCase()
    if (!text) return true
    return [route.name, route.route_code, route.status].join(' ').toLowerCase().includes(text)
  })
  const pending = data.requests.filter((x: any) => x.status === 'PENDING')
  const seats = data.vehicles.reduce((n: number, v: any) => n + Math.max(0, v.capacity - v.occupied), 0)

  return (
    <div className="fade-in">
      <PageHead
        title="Transport Overview"
        sub="A quick view of fleet readiness, active route coverage, and pending student transport needs."
        right={
          <div className="transport-top-search">
            <FiSearch />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search transport..."
              aria-label="Search transport"
            />
          </div>
        }
      />

      {loading ? <Spinner /> : (
        <>
          <div className="kpi-row transport-clickable-kpis">
            {[
              ['Operational Routes', data.routes.length, 'routes'], ['Vehicles', data.vehicles.length, 'vehicles'],
              ['Drivers', data.drivers.length, 'drivers'], ['Pending Requests', pending.length, 'requests'],
              ['Allocated Students', data.allocations.length, 'students'], ['Available Seats', seats, 'vehicles'],
            ].map(([label, value, target]) => <button className="kpi" key={label} aria-label={label} onClick={() => { sessionStorage.setItem('transport-tab', target as string); go?.('transport') }}><div className="kpi-v">{value}</div></button>)}
          </div>

          <div className="transport-overview-grid">
            <section className="card transport-overview-panel">
              <div className="card-h">
                <h3>Route Coverage</h3>
              </div>
              <div className="card-pad transport-list-wrap">
                {visibleRoutes.length > 0 ? visibleRoutes.map((route: any) => (
                  <div key={route.id} className="transport-mini-row">
                    <div>
                      <strong>{route.route_code}</strong>
                      <span>{route.name}</span>
                    </div>
                    <Pill s={route.status || 'ACTIVE'} />
                  </div>
                )) : <Empty text="No matching routes" />}
              </div>
            </section>

            <section className="card transport-overview-panel">
              <div className="card-h">
                <h3>Fleet Snapshot</h3>
              </div>
              <div className="card-pad transport-list-wrap">
                {data.vehicles.length > 0 ? data.vehicles.map((vehicle: any) => (
                  <div key={vehicle.id} className="transport-mini-row">
                    <div>
                      <strong>{vehicle.vehicle_number}</strong>
                      <span>{vehicle.vehicle_type} Â· {Math.max(0, vehicle.capacity - vehicle.occupied)} seats free</span>
                    </div>
                    <Pill s={vehicle.status || 'AVAILABLE'} />
                  </div>
                )) : <Empty text="No vehicles assigned" />}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  )
}

function StudentTransport() {
  const [allocation, setAllocation] = useState<any>(null)
  const [requests, setRequests] = useState<any[]>([])
  const [routes, setRoutes] = useState<any[]>([])
  const [routeId, setRouteId] = useState('')
  const [stopId, setStopId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [showRequest, setShowRequest] = useState(false)
  const [reason, setReason] = useState('')
  const [liveLocation, setLiveLocation] = useState<any>(null)
  const load = async () => { try { const [mine, reqs, routeData] = await Promise.all([api.myTransportAllocation(), api.transportRequests(), api.transportRoutes()]); setAllocation(mine?.allocation ?? (mine?.id ? mine : null)); setRequests(reqs.requests || []); setRoutes(routeData.routes || []); setError('') } catch (e: any) { setError(e.message || 'Unable to load transport assignments.') } }
  useEffect(() => { load() }, [])
  useEffect(() => { if (!allocation?.vehicle_id) return; const poll = () => api.liveTransportLocation(allocation.vehicle_id).then(setLiveLocation).catch(() => setLiveLocation(null)); poll(); const timer = window.setInterval(poll, 10000); return () => window.clearInterval(timer) }, [allocation?.vehicle_id])
  const pending = requests.some((r) => r.status === 'PENDING')
  const route = routes.find((r) => r.id === routeId)
  const submit = async () => { if (!routeId || !stopId) return setError('Please select a route and pickup point.') ; try { setBusy(true); await api.createTransportRequest({ route_id: routeId, pickup_stop_id: stopId, drop_stop_id: stopId, message: reason }); setShowRequest(false); setReason(''); await load() } catch (e: any) { setError(e.message || 'Unable to submit request.') } finally { setBusy(false) } }
  if (allocation) return <StudentAssignedTransport allocation={allocation} routes={routes} />
  return <div className="student-transport-portal fade-in"><header className="student-portal-head"><div><h1>My Transport</h1><p>You currently don't have an active transport allocation.</p></div></header><section className="student-portal-empty"><FaBus /><h2>You are not assigned to any bus.</h2>{error && <p className="notice rose">{error}</p>}{pending ? <div className="student-pending"><FiCheckCircle /> Transport request pending</div> : <><p>Request a bus assignment by selecting your preferred route and pickup point.</p><div className="student-request-form"><select className="select" value={routeId} onChange={(e) => { setRouteId(e.target.value); setStopId('') }}><option value="">Select route</option>{routes.map((r: any) => <option key={r.id} value={r.id}>{r.route_code} Â· {r.name}</option>)}</select><select className="select" value={stopId} onChange={(e) => setStopId(e.target.value)} disabled={!route}><option value="">Select pickup point</option>{route?.stops?.map((s: any) => <option key={s.id} value={s.id}>{s.sequence}. {s.name}</option>)}</select><button className="btn btn-crimson" onClick={submit} disabled={busy}><FiSend /> {busy ? 'Sending...' : 'Request Bus Approval'}</button></div></>}</section></div>
}

function StudentAssignedTransport({ allocation, routes }: { allocation: any; routes: any[] }) {
  const [live, setLive] = useState<any>(null)
  const stops = allocation.route_stops || routes.find((r: any) => r.id === allocation.route_id)?.stops || []
  useEffect(() => { const poll = () => api.liveTransportLocation(allocation.vehicle_id).then(setLive).catch(() => setLive(null)); poll(); const timer = window.setInterval(poll, 10000); return () => window.clearInterval(timer) }, [allocation.vehicle_id])
  const current = live?.current_stop
  const next = live?.next_stop
  return <div className="student-transport-portal fade-in"><header className="student-portal-head"><div><h1>My Transport</h1><p>Your active bus assignment and route details</p></div></header><div className="student-portal-grid"><section className="student-portal-card student-portal-vehicle"><FaBus /><div><span>Assigned Vehicle</span><h2>{allocation.vehicle || 'Vehicle unavailable'}</h2><Pill s={allocation.vehicle_status || allocation.status || 'ACTIVE'} /></div></section><section className="student-portal-card student-live-card"><h3><FiRadio /> Live Bus Tracking {live?.status === 'RUNNING' && <span className="student-live-indicator">Live</span>}</h3>{live?.status === 'RUNNING' && live.location ? <><div className="student-live-map"><FiNavigation /><span>Current location received</span></div><div className="student-live-coordinates">{live.location.latitude.toFixed(5)}, {live.location.longitude.toFixed(5)}</div><p>Current / nearest stop: <b>{current?.name || 'Calculating'}</b></p><p>Next stop: <b>{next?.name || 'End of route'}</b></p>{current?.distance_km != null && <p>Distance: <b>{current.distance_km.toFixed(2)} km</b></p>}</> : <p>{live?.status === 'ENDED' ? 'Bus tracking has ended.' : 'Bus tracking has not started yet.'}</p>}</section><section className="student-portal-card"><h3><FiMapPin /> Route</h3><strong>{allocation.route || 'Route unavailable'}</strong><div className="student-route-stops">{stops.map((s: any) => <div key={s.id} className={s.id === allocation.pickup_stop_id ? 'pickup-stop selected' : 'pickup-stop'}><span>{String(s.sequence).padStart(2, '0')}</span><FiClock /><b>{s.pickup_time || 'â€”'}</b><label>{s.name}</label>{s.id === allocation.pickup_stop_id && <FiCheckCircle />}</div>)}</div></section><section className="student-portal-card"><h3><FiUser /> Driver</h3><strong>{allocation.driver || 'Not assigned'}</strong>{allocation.driver_phone && <span><FiPhone /> {allocation.driver_phone}</span>}</section><section className="student-portal-card student-pickup-card"><h3>Your Pickup Point</h3><strong><FiMapPin /> {allocation.pickup || 'Not specified'}</strong>{allocation.pickup_time && <span><FiClock /> {allocation.pickup_time}</span>}</section></div></div>
}

function LiveBusLocation({ vehicleId }: { vehicleId: string }) {
  const [live, setLive] = useState<any>(null)
  useEffect(() => { const poll = () => api.liveTransportLocation(vehicleId).then(setLive).catch(() => setLive(null)); poll(); const timer = window.setInterval(poll, 10000); return () => window.clearInterval(timer) }, [vehicleId])
  return <section className="student-portal-card student-live-card"><h3><FiRadio /> Live Bus Location</h3>{live?.status === 'RUNNING' && live.location ? <><div className="student-live-map"><FiMapPin /><span>GPS location received</span></div><div className="student-live-coordinates">{live.location.latitude.toFixed(5)}, {live.location.longitude.toFixed(5)}</div><small>Last updated {new Date(live.location.recorded_at).toLocaleTimeString()}</small></> : <p>{live?.status === 'ENDED' ? 'Bus tracking has ended.' : 'Bus tracking has not started yet.'}</p>}</section>
}

function TransportManager() {
  const [tab, setTab] = useState<Tab>(() => (sessionStorage.getItem('transport-tab') as Tab) || 'dashboard')
  useEffect(() => { sessionStorage.removeItem('transport-tab') }, [])
  const [modal, setModal] = useState<ModalType>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [selectedRoute, setSelectedRoute] = useState<any>(null)
  const [selectedStop, setSelectedStop] = useState<any>(null)
  const [selectedVehicle, setSelectedVehicle] = useState<any>(null)
  const [studentAssignVehicleId, setStudentAssignVehicleId] = useState('')
  const [selectedAllocation, setSelectedAllocation] = useState<any>(null)
  const [expandedRoutes, setExpandedRoutes] = useState<Record<string, boolean>>({})
  const [expandedVehicles, setExpandedVehicles] = useState<Record<string, boolean>>({})
  const [selectedRequest, setSelectedRequest] = useState<any>(null)
  const [selectedStudent, setSelectedStudent] = useState<any>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<{ type: string; id: string; name: string; routeId?: string } | null>(null)
  const [transportSearch, setTransportSearch] = useState('')
  const [studentSearch, setStudentSearch] = useState('')
  const [allocationStudentSearch, setAllocationStudentSearch] = useState('')
  const [studentFilters, setStudentFilters] = useState({
    student: 'All',
    route: 'All',
    stop: 'All',
    year: 'All',
    fee: 'All',
  })
  
  const [data, setData] = useState({
    routes: [],
    vehicles: [],
    drivers: [],
    requests: [],
    allocations: [],
    stops: [],
    students: [],
  })

  const load = async () => {
    try {
      setLoading(true)
      const [r, v, dr, q, a, st] = await Promise.all([
        api.transportRoutes(),
        api.transportVehicles(),
        api.transportDrivers(),
        api.transportRequests(),
        api.transportAllocations(),
        api.students?.() || Promise.resolve({ students: [] }),
      ])
      setData({
        routes: r.routes || [],
        vehicles: v.vehicles || [],
        drivers: dr.drivers || [],
        requests: q.requests || [],
        allocations: a.allocations || [],
        stops: [],
        students: st.students || [],
      })
      setError('')
    } catch (e: any) {
      setError('Failed to load transport data')
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])


  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(''), 3000)
      return () => clearTimeout(timer)
    }
  }, [success])

  useEffect(() => {
    if (!data.routes.length) return
    setExpandedRoutes((current) => {
      const next = { ...current }
      const firstId = data.routes[0].id
      if (!(firstId in next)) next[firstId] = true
      return next
    })
  }, [data.routes])

  const closeModal = () => {
    setModal(null)
    setForm(emptyForm)
    setSelectedRoute(null)
    setSelectedStop(null)
    setSelectedVehicle(null)
    setSelectedAllocation(null)
    setSelectedStudent(null)
    setStudentAssignVehicleId('')
    setAllocationStudentSearch('')
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      setLoading(true)
      const { type, id } = deleteConfirm
      
      if (type === 'route') {
        // A route may already be soft-deleted by another view/session. Treat
        // that state as complete so the stale card does not leave the user
        // stuck on a "not found" error.
        try {
          await api.deleteTransportRoute?.(id)
        } catch (e: any) {
          if (!String(e?.message || '').toLowerCase().includes('not found')) throw e
        }
      } else if (type === 'stop') {
        if (!deleteConfirm.routeId) throw new Error('Route is required to delete this pickup point')
        await api.deleteTransportStop?.(deleteConfirm.routeId, id, deleteConfirm.name)
      } else if (type === 'allocation') {
        await api.deleteTransportAllocation?.(id)
      }
      
      setSuccess(`${deleteConfirm.name} deleted successfully`)
      setDeleteConfirm(null)
      load()
    } catch (e: any) {
      setError(e.message || 'Delete failed')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setError('')
      setLoading(true)

      if (modal === 'driver') {
        const createdDriver = await api.createTransportDriver({
          name: form.name,
          employee_id: form.employee_id,
          phone: form.phone,
          license_number: form.license_number,
          license_expiry: form.license_expiry || null,
          vehicle_id: form.vehicle_id || null,
        })
        setSuccess(`Driver created. Login username: ${createdDriver.username} Â· Password: ${createdDriver.initial_password}`)
      } else if (modal === 'vehicle') {
        const payload = {
          vehicle_number: form.vehicle_number,
          vehicle_type: form.vehicle_type,
          capacity: Number(form.capacity),
          status: form.status || 'AVAILABLE',
          driver_id: form.driver_id || null,
        }
        if (selectedVehicle) await api.updateTransportVehicle(selectedVehicle.id, payload)
        else {
          const createdVehicle = await api.createTransportVehicle({ ...payload, driver_id: null })
          if (payload.driver_id) await api.updateTransportVehicle(createdVehicle.id, payload)
        }
        setSuccess(selectedVehicle ? 'Vehicle updated successfully' : 'Vehicle created successfully')
      } else if (modal === 'route') {
        await api.createTransportRoute({
          name: form.name,
          route_code: form.route_code,
          description: form.status || '',
          vehicle_no: form.vehicle_id || '',
          status: 'ACTIVE',
        })
        setSuccess('Route created successfully')
      } else if (modal === 'stop' && selectedRoute) {
        const payload = {
          name: form.stop_name,
          address: form.stop_address,
          sequence: selectedStop ? Number(form.sequence) : ((selectedRoute?.stops || []).filter((s: any) => s.status !== 'INACTIVE').length + 1),
          pickup_time: form.pickup_time,
          drop_time: form.drop_time,
          status: 'ACTIVE',
        }
        if (selectedStop) {
          await api.updateTransportStop(selectedRoute.id, selectedStop.id, payload)
          setSuccess('Stop updated successfully')
        } else {
          await api.createTransportStop(selectedRoute.id, payload)
          setSuccess('Stop added successfully')
        }
      } else if (modal === 'student-assign') {
        const stopId = form.pickup_stop_id || form.drop_stop_id
        if (!form.student_id || !form.route_id || !form.vehicle_id || !stopId) {
          setError('Student, route, vehicle, and stop are required')
          return
        }
        const payload = {
          student_id: form.student_id,
          route_id: form.route_id,
          vehicle_id: form.vehicle_id,
          pickup_stop_id: stopId,
          drop_stop_id: stopId,
          driver_id: form.driver_id || null,
          start_date: form.start_date || null,
          end_date: form.end_date || null,
        }
        if (selectedAllocation) {
          await api.updateTransportAllocation(selectedAllocation.id, payload)
          setSuccess('Student assignment updated successfully')
        } else {
          await api.createTransportAllocation(payload)
          setSuccess('Student assigned successfully')
        }
      }

      closeModal()
      load()
    } catch (e: any) {
      const errorMsg = e.message || 'Operation failed'
      if (errorMsg.includes('409')) {
        setError('This item already exists or is in use')
      } else if (errorMsg.includes('403')) {
        setError('You do not have permission for this action')
      } else {
        setError(errorMsg)
      }
    } finally {
      setLoading(false)
    }
  }

  const pending = data.requests.filter((x: any) => x.status === 'PENDING')
  const seats = data.vehicles.reduce((n: number, v: any) => n + Math.max(0, v.capacity - v.occupied), 0)
  const filterText = transportSearch.trim().toLowerCase()
  const filteredRequests = filterText
    ? data.requests.filter((row: any) => [row.student_name, row.student_id, row.status].join(' ').toLowerCase().includes(filterText))
    : data.requests
  const filteredRoutes = filterText
    ? data.routes.filter((row: any) => [row.name, row.route_code, row.status].join(' ').toLowerCase().includes(filterText))
    : data.routes
  const filteredVehicles = filterText
    ? data.vehicles.filter((row: any) => [row.vehicle_number, row.vehicle_type, row.status].join(' ').toLowerCase().includes(filterText))
    : data.vehicles
  const filteredDrivers = filterText
    ? data.drivers.filter((row: any) => [row.name, row.employee_id, row.phone].join(' ').toLowerCase().includes(filterText))
    : data.drivers

  return (
    <div className="fade-in">
      <PageHead
        title="Transport Management"
        sub="Manage routes, vehicles, drivers, and student allocations"
        right={
          <div className="transport-top-search">
            <FiSearch />
            <input
              type="text"
              value={transportSearch}
              onChange={(e) => setTransportSearch(e.target.value)}
              placeholder="Search transport..."
              aria-label="Search transport"
            />
          </div>
        }
      />

      <div className="tabs">
        {(['dashboard', 'requests', 'routes', 'vehicles', 'drivers', 'students', 'allocations'] as Tab[]).map((t) => (
          <button
            key={t}
            className={tab === t ? 'tab on' : 'tab'}
            onClick={() => setTab(t)}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {error && (
        <div className="notice rose">
          {error}
          <button
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', fontSize: 16 }}
            onClick={() => setError('')}
          >
            âœ•
          </button>
        </div>
      )}
      {success && (
        <div className="notice" style={{ background: '#e4f5ef', borderColor: '#16a34a', color: '#15803d' }}>
          {success}
        </div>
      )}

      {tab === 'dashboard' && (
        <>
          <div className="kpi-row transport-clickable-kpis">
            {[
              ['Routes', data.routes.length, 'routes'], ['Vehicles', data.vehicles.length, 'vehicles'], ['Drivers', data.drivers.length, 'drivers'],
              ['Allocated', data.allocations.length, 'students'], ['Pending Requests', pending.length, 'requests'], ['Available Seats', seats, 'vehicles'],
            ].map(([label, value, target]) => <button className="kpi" key={label} onClick={() => setTab(target as Tab)}><div className="kpi-v">{value}</div><div className="kpi-l">{label}</div></button>)}
          </div>
          <div className="transport-dashboard-links">
            {[['routes', 'Manage routes'], ['vehicles', 'Manage vehicles'], ['drivers', 'Manage drivers'], ['students', 'View students'], ['requests', 'Review requests'], ['allocations', 'View allocations']].map(([key, label]) => (
              <button key={key} className="btn btn-out" onClick={() => setTab(key as Tab)}>{label} <span>â†’</span></button>
            ))}
          </div>

          <Section title="Pending Transport Requests">
            {filteredRequests.filter((x: any) => x.status === 'PENDING').length > 0 ? (
              <RequestsTable rows={filteredRequests.filter((x: any) => x.status === 'PENDING')} routes={data.routes} onApprove={(r) => {
                setSelectedRequest(r)
                setModal('request')
              }} />
            ) : (
              <EmptyState text={filterText ? 'No matching pending requests' : 'No pending requests'} />
            )}
          </Section>

          <Section title="Vehicle Occupancy">
            <OccupancyCards vehicles={filteredVehicles} emptyText={filterText ? 'No matching vehicles' : 'No vehicles added'} />
          </Section>
        </>
      )}

      {tab === 'requests' && (
        <Section title="All Transport Requests">
          {filteredRequests.length > 0 ? (
            <RequestsTable rows={filteredRequests} routes={data.routes} onApprove={(r) => {
              setSelectedRequest(r)
              setModal('request')
            }} />
          ) : (
            <EmptyState text={filterText ? 'No matching transport requests' : 'No transport requests'} />
          )}
        </Section>
      )}

      {tab === 'routes' && (
        <Section
          title="Routes"
          action={
            <button className="btn btn-sm btn-crimson" onClick={() => setModal('route')}>
              + Create Route
            </button>
          }
        >
          {filteredRoutes.length > 0 ? (
            <div className="transport-routes-list">
              {filteredRoutes.map((route: any) => {
                const sortedStops = [...(route.stops || [])].sort((a: any, b: any) => Number(a.sequence) - Number(b.sequence))
                return (
                  <div className="card transport-route-card" key={route.id}>
                    <button
                      className="transport-route-header"
                      onClick={() => setExpandedRoutes((current) => ({ ...current, [route.id]: !current[route.id] }))}
                      aria-expanded={Boolean(expandedRoutes[route.id])}
                    >
                      <div className="transport-route-heading">
                        <span className="transport-route-badge"><FaBus /></span>
                        <div className="transport-route-meta">
                          <div className="transport-route-mainline">
                            <b>{route.route_code}</b>
                            <Pill s={route.status} />
                          </div>
                          <span>{route.name}</span>
                        </div>
                      </div>

                      <div className="transport-route-right">
                        <span>{sortedStops.length} pickup points</span>
                        <span className="transport-route-chevron">{expandedRoutes[route.id] ? <FiChevronUp /> : <FiChevronDown />}</span>
                      </div>
                    </button>

                    {expandedRoutes[route.id] && (
                      <div className="transport-route-body">
                        <div className="transport-route-body-header">
                          <div>
                            <h4>Boarding Points</h4>
                            <small>Daily pickup schedule â€¢ ordered from first to last stop</small>
                          </div>
                          <button
                            className="btn btn-sm btn-crimson"
                            onClick={() => { setSelectedRoute(route); setModal('stop') }}
                          >
                            <FiPlus /> Add Pickup Point
                          </button>
                        </div>

                        {sortedStops.length > 0 ? (
                          <div className="transport-stop-timeline">
                            {sortedStops.map((stop: any, index: number) => (
                              <div className="transport-stop" key={stop.id}>
                                <div className="transport-stop-rail"><div className="transport-stop-marker">{String(stop.sequence || index + 1).padStart(2, '0')}</div>{index < sortedStops.length - 1 && <div className="transport-stop-line" />}</div>
                                <div className="transport-stop-content">
                                  <div className="transport-stop-copy">
                                    <div className="transport-stop-time-inline">
                                      <span className="transport-stop-clock">{stop.pickup_time || 'â€”'}</span>
                                      <span className="transport-stop-daily">Daily</span>
                                    </div>
                                    <div className="transport-stop-name-wrap">
                                      <FiMapPin />
                                      <div><b>{stop.name}</b>
                                      <small>Pickup Point {stop.sequence || index + 1}</small></div>
                                    </div>
                                  </div>

                                  {stop.address && <div className="transport-stop-address">{stop.address}</div>}
                                  <div className="transport-stop-actions">
                                    <button
                                      className="icon-btn"
                                      title="Edit stop"
                                      onClick={() => {
                                        setSelectedRoute(route)
                                        setSelectedStop(stop)
                                        setForm({ ...emptyForm, stop_name: stop.name, stop_address: stop.address || '', sequence: stop.sequence, pickup_time: stop.pickup_time || '', drop_time: stop.drop_time || '' })
                                        setModal('stop')
                                      }}
                                    >
                                      <FiEdit2 />
                                    </button>
                                    <button
                                      className="icon-btn danger"
                                      title="Delete stop"
                                      onClick={() => setDeleteConfirm({ type: 'stop', id: stop.id, routeId: route.id, name: stop.name })}
                                    >
                                      <FiTrash2 />
                                    </button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="transport-stop-empty"><span><FiMapPin /></span><h4>No pickup points added</h4><p>Add boarding points to define the pickup schedule for this route.</p><button className="btn btn-sm btn-crimson" onClick={() => { setSelectedRoute(route); setModal('stop') }}><FiPlus /> Add Pickup Point</button></div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState text={filterText ? 'No matching routes' : 'No routes created'} />
          )}
        </Section>
      )}

      {tab === 'vehicles' && (
        <Section
          title="Vehicles"
          action={
            <button className="btn btn-sm btn-crimson" onClick={() => setModal('vehicle')}>
              + Create Vehicle
            </button>
          }
        >
          {filteredVehicles.length > 0 ? (
            <div className="card">
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Vehicle Number</th>
                      <th>Type</th>
                      <th>Capacity</th>
                      <th>Occupied</th>
                      <th>Available</th>
                      <th>Status</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredVehicles.map((v: any) => (
                      <tr key={v.id}>
                        <td><b>{v.vehicle_number}</b></td>
                        <td>{v.vehicle_type}</td>
                        <td>{v.capacity}</td>
                        <td>{v.occupied}</td>
                        <td>{Math.max(0, v.capacity - v.occupied)}</td>
                        <td><Pill s={v.status} /></td>
                        <td><button className="link-btn" onClick={() => { setSelectedVehicle(v); setForm({ ...emptyForm, vehicle_number: v.vehicle_number, vehicle_type: v.vehicle_type, capacity: v.capacity, status: v.status, driver_id: v.driver_id || '' }); setModal('vehicle') }}>Edit</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState text={filterText ? 'No matching vehicles' : 'No vehicles added'} />
          )}
        </Section>
      )}

      {tab === 'drivers' && (
        <Section
          title="Drivers"
          action={
            <button className="btn btn-sm btn-crimson" onClick={() => setModal('driver')}>
              + Create Driver
            </button>
          }
        >
          {filteredDrivers.length > 0 ? (
            <div className="card">
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Driver ID</th>
                      <th>Phone</th>
                      <th>License</th>
                      <th>License Expiry</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDrivers.map((d: any) => (
                      <tr key={d.id}>
                        <td><b>{d.name}</b></td>
                        <td className="mono">{d.employee_id}</td>
                        <td>{d.phone}</td>
                        <td className="mono">{d.license_number}</td>
                        <td className="mono">{d.license_expiry || 'ï¿½'}</td>
                        <td><Pill s={d.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState text={filterText ? 'No matching drivers' : 'No drivers added'} />
          )}
        </Section>
      )}

      {tab === 'students' && (
        <>
          {(() => {
            const filteredAllocations = (() => {
              let result = data.allocations || []
              if (studentSearch) {
                const search = studentSearch.toLowerCase()
                result = result.filter((a: any) => 
                  a.student_name?.toLowerCase().includes(search) || 
                  a.student_id?.toLowerCase().includes(search)
                )
              }
              if (studentFilters.student !== 'All') result = result.filter((a: any) => a.student_id === studentFilters.student)
              if (studentFilters.route !== 'All') result = result.filter((a: any) => a.route_id === studentFilters.route)
              if (studentFilters.stop !== 'All') result = result.filter((a: any) => a.pickup_stop_id === studentFilters.stop)
              return result
            })()
            
            const allocationsByVehicle = (() => {
              const grouped: Record<string, any[]> = {}
              filteredAllocations.forEach((a: any) => {
                const vehicleId = a.vehicle_id
                if (!grouped[vehicleId]) grouped[vehicleId] = []
                grouped[vehicleId].push(a)
              })
              return grouped
            })()
            
            const getUniqueValues = (field: string) => {
              const values = new Set(data.allocations?.map((a: any) => a[field]).filter(Boolean))
              return Array.from(values)
            }

            return (
              <Section title={`Student Transport Â· ${filteredAllocations.length} ${filteredAllocations.length === 1 ? 'record' : 'records'}`} action={<button className="btn btn-sm btn-crimson" onClick={() => setModal('vehicle')}><FiPlus /> New Vehicle</button>}>
                <div className="card">
                  <div className="card-pad" style={{ borderBottom: '1px solid var(--line)' }}>
                    <div className="student-transport-search"><FiSearch /><input type="text" placeholder="Search student transport..." value={studentSearch} onChange={(e) => setStudentSearch(e.target.value)} /></div>
                    
                    <div className="student-transport-filters"><span className="student-filter-label"><FiFilter /> Filters</span>
                      <div className="transport-filter">
                        <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-mute)', marginBottom: 6 }}>Student</label>
                        <select className="select" value={studentFilters.student} onChange={(e) => setStudentFilters({ ...studentFilters, student: e.target.value })}>
                          <option value="All">All</option>
                          {getUniqueValues('student_id').map((s: any) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                      <div className="transport-filter">
                        <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-mute)', marginBottom: 6 }}>Route</label>
                        <select className="select" value={studentFilters.route} onChange={(e) => setStudentFilters({ ...studentFilters, route: e.target.value })}>
                          <option value="All">All</option>
                          {data.routes.filter((r: any) => r.status !== 'INACTIVE').map((r: any) => <option key={r.id} value={r.id}>{r.route_code ? `${r.route_code} Â· ` : ''}{r.name}</option>)}
                        </select>
                      </div>
                      <div className="transport-filter">
                        <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--txt-mute)', marginBottom: 6 }}>Stop</label>
                        <select className="select" value={studentFilters.stop} onChange={(e) => setStudentFilters({ ...studentFilters, stop: e.target.value })}>
                          <option value="All">All</option>
                          {getUniqueValues('pickup_stop_id').map((s: any) => {
                            const stop = data.allocations.find((x: any) => x.pickup_stop_id === s)
                            return <option key={s} value={s}>{stop?.pickup || s}</option>
                          })}
                        </select>
                      </div>
                      <button className="btn btn-sm btn-out" onClick={() => setStudentFilters({ student: 'All', route: 'All', stop: 'All', year: 'All', fee: 'All' })}>Clear Filters</button>
                    </div>
                  </div>

                  {data.vehicles.length > 0 ? (
                    data.vehicles.map((vehicle: any) => {
                      const vehicleId = vehicle.id
                      const allocations = allocationsByVehicle[vehicleId] || []
                      return (
                        <div key={vehicleId} className="student-vehicle-group">
                          <button
                            onClick={() => setExpandedVehicles((current) => ({ ...current, [vehicleId]: !current[vehicleId] }))}
                            className="student-vehicle-header"
                            aria-expanded={Boolean(expandedVehicles[vehicleId])}
                          >
                            <div className="student-vehicle-header-main">
                              <span className="student-route-badge"><FaBus /></span>
                              <div>
                                <div className="student-vehicle-name">
                                  {vehicle?.vehicle_number || 'Vehicle'}
                                  <span className="student-vehicle-status">{vehicle?.status?.toLowerCase() || 'active'}</span>
                                </div>
                                <small>{allocations.length} {allocations.length === 1 ? 'student' : 'students'} Â· {vehicle?.vehicle_type || 'Bus'}</small>
                              </div>
                            </div>
                            <div className="student-vehicle-header-side">
                              <span>{allocations.length} in route</span>
                              <span className="student-vehicle-chevron">{expandedVehicles[vehicleId] ? <FiChevronUp /> : <FiChevronDown />}</span>
                            </div>
                          </button>
                          {expandedVehicles[vehicleId] && (
                            <div className="student-vehicle-body">
                              <div className="assigned-students-head">
                                <b><FiUsers /> Assigned Students</b>
                                <button className="btn btn-sm btn-crimson" onClick={(e) => { e.stopPropagation(); const assignedRoute = data.routes.find((r: any) => r.status !== 'INACTIVE' && r.vehicle_no === vehicle.vehicle_number); setStudentAssignVehicleId(vehicleId); setForm({ ...emptyForm, vehicle_id: vehicleId, route_id: assignedRoute?.id || '', driver_id: vehicle.driver_id || '' }); setModal('student-assign') }}><FiPlus /> Add Student</button>
                              </div>
                              <div className="student-assignment-list">
                                {allocations.map((alloc: any) => (
                                  <div key={alloc.id} className="student-row" role="button" tabIndex={0} onClick={() => { setSelectedStudent(alloc); setModal('student-details') }} onKeyDown={(e) => { if (e.key === 'Enter') { setSelectedStudent(alloc); setModal('student-details') } }}>
                                    <div className="student-info">
                                      <span className="student-avatar"><FiUser /></span>
                                      <div className="student-details">
                                        <strong className="student-name student-detail-link" role="button" tabIndex={0} onClick={(e) => { e.stopPropagation(); setSelectedStudent(alloc); setModal('student-details') }} onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); setSelectedStudent(alloc); setModal('student-details') } }}>{alloc.student_name}</strong>
                                        <span className="student-id">{alloc.roll_no || alloc.student_id}</span>
                                        <span className="pickup-point"><FiMapPin /> {alloc.pickup || 'Pickup stop'}</span>
                                      </div>
                                    </div>
                                    <div className="student-row-right">
                                      <span className="student-assigned-date">{alloc.assigned_at?.split('T')[0] || 'Current'}</span>
                                      <div className="student-actions">
                                        <button className="student-icon-btn" aria-label="Edit student" title="Edit" onClick={(e) => { e.stopPropagation(); setSelectedAllocation(alloc); setForm({ ...emptyForm, student_id: alloc.student_id, route_id: alloc.route_id, pickup_stop_id: alloc.pickup_stop_id, drop_stop_id: alloc.drop_stop_id, vehicle_id: alloc.vehicle_id, driver_id: alloc.driver_id || '' }); setModal('student-assign') }}><FiEdit2 /></button>
                                        <button className="student-icon-btn danger" aria-label="Delete student" title="Delete" onClick={(e) => { e.stopPropagation(); setDeleteConfirm({ type: 'allocation', id: alloc.id, name: `${alloc.student_name}'s assignment` }) }}><FiTrash2 /></button>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })
                  ) : (
                    <div className="card-pad">
                      <Empty text="No student assignments" />
                    </div>
                  )}
                </div>
              </Section>
            )
          })()}
        </>
      )}

      {tab === 'allocations' && (
        <Section title="Student Allocations">
          {data.allocations.length > 0 ? (
            <div className="card">
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th>Roll No.</th>
                      <th>Route</th>
                      <th>Vehicle</th>
                      <th>Driver</th>
                      <th>Pickup point</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.allocations.map((a: any) => (
                      <tr key={a.id}>
                        <td><b>{a.student_name}</b></td>
                        <td className="mono">{a.roll_no || a.student_id}</td>
                        <td>{a.route}</td>
                        <td>{a.vehicle}</td>
                        <td>{a.driver || 'Not assigned'}</td>
                        <td>{a.pickup || 'Not assigned'}</td>
                        <td><Pill s={a.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState text="No allocations" />
          )}
        </Section>
      )}

      {/* DELETE CONFIRMATION */}
      {deleteConfirm && (
        <div className="modal-bg" onClick={() => setDeleteConfirm(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-h">
              <h3>Confirm Delete</h3>
              <button className="modal-x" onClick={() => setDeleteConfirm(null)}>âœ•</button>
            </div>
            <div className="modal-b">
              <p>Are you sure you want to delete <b>{deleteConfirm.name}</b>?</p>
            </div>
            <div className="modal-f">
              <button className="btn btn-out" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-rose" onClick={handleDelete} disabled={loading}>{loading ? 'Deleting...' : 'Delete'}</button>
            </div>
          </div>
        </div>
      )}

      {modal === 'request' && selectedRequest && (
        <div className="modal-bg" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-h">
              <h3>Approve Request</h3>
              <button className="modal-x" onClick={closeModal}>âœ•</button>
            </div>
            <div className="modal-b">
              <RequestApprovalForm
                request={selectedRequest}
                routes={data.routes}
                vehicles={data.vehicles}
                drivers={data.drivers}
                onApprove={async (payload) => {
                  try {
                    await api.approveTransportRequest(selectedRequest.id, payload)
                    setSuccess('Request approved')
                    closeModal()
                    load()
                  } catch (e: any) {
                    setError(e.message)
                  }
                }}
                onReject={async () => {
                  try {
                    await api.rejectTransportRequest(selectedRequest.id)
                    setSuccess('Request rejected')
                    closeModal()
                    load()
                  } catch (e: any) {
                    setError(e.message)
                  }
                }}
              />
            </div>
          </div>
        </div>
      )}

      {modal === 'student-details' && selectedStudent && (
        <div className="modal-bg" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-h"><h3>Student Transport Details</h3><button className="modal-x" onClick={closeModal}>âœ•</button></div>
            <div className="modal-b">
              <div className="student-detail-hero"><span className="assigned-student-icon"><FiUser /></span><div><h3>{selectedStudent.student_name || 'Student'}</h3><span className="mono">Roll No: {selectedStudent.roll_no || selectedStudent.student_id}</span></div></div>
              <div className="student-detail-grid"><div><small>Route</small><b>{selectedStudent.route || selectedStudent.route_id || 'â€”'}</b></div><div><small>Vehicle</small><b>{selectedStudent.vehicle || selectedStudent.vehicle_id || 'â€”'}</b></div><div><small>Pickup point</small><b>{selectedStudent.pickup || selectedStudent.pickup_stop_id || 'â€”'}</b></div><div><small>Status</small><Pill s={selectedStudent.status || 'ACTIVE'} /></div></div>
            </div>
            <div className="modal-f"><button className="btn btn-out" onClick={closeModal}>Close</button></div>
          </div>
        </div>
      )}

      {modal && modal !== 'request' && modal !== 'student-details' && (
        <div className="modal-bg" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-h">
              <h3>
                {modal === 'driver'
                  ? 'Add Driver'
                  : modal === 'vehicle'
                    ? (selectedVehicle ? 'Edit Vehicle' : 'Add Vehicle')
                    : modal === 'route'
                      ? 'Create Route'
                      : modal === 'stop'
                        ? `${selectedStop ? 'Edit stop' : 'Add stop'} Â· ${selectedRoute?.route_code}`
                        : 'Add Student Assignment'}
              </h3>
              <button className="modal-x" onClick={closeModal}>âœ•</button>
            </div>

            <div className="modal-b">
              {modal === 'driver' && (
                <div>
                  <div className="grid-2">
                    <FormField label="Driver Name *" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
                    <FormField label="Driver ID *" value={form.employee_id} onChange={(v) => setForm({ ...form, employee_id: v })} />
                    <FormField label="Phone *" type="tel" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} />
                    <FormField label="License Number *" value={form.license_number} onChange={(v) => setForm({ ...form, license_number: v })} />
                    <FormField label="License Expiry" type="date" value={form.license_expiry} onChange={(v) => setForm({ ...form, license_expiry: v })} />
                  </div>
                  <div className="form-row">
                    <label>Assign Vehicle (Optional)</label>
                    <select className="select" value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}>
                      <option value="">Not assigned</option>
                      {data.vehicles.map((v: any) => {
                        const isAssigned = Boolean(v.driver_id) || data.drivers.some((d: any) => d.vehicle_id === v.id && d.id !== form.driver_id)
                        return !isAssigned ? (
                          <option key={v.id} value={v.id}>
                            {v.vehicle_number} ({v.vehicle_type}, {v.capacity} seats)
                          </option>
                        ) : null
                      })}
                    </select>
                  </div>
                </div>
              )}

              {modal === 'vehicle' && (
                <div className="grid-2">
                  <FormField label="Vehicle Number *" value={form.vehicle_number} onChange={(v) => setForm({ ...form, vehicle_number: v })} />
                  <FormField label="Vehicle Type *" value={form.vehicle_type} onChange={(v) => setForm({ ...form, vehicle_type: v })} />
                  <FormField label="Capacity *" type="number" value={form.capacity} onChange={(v) => setForm({ ...form, capacity: v })} />
                  <div className="form-row"><label>Status</label><select className="select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="AVAILABLE">Available</option><option value="ASSIGNED">Assigned</option><option value="MAINTENANCE">Maintenance</option><option value="INACTIVE">Inactive</option></select></div>
                  <div className="form-row"><label>Driver (Optional)</label><select className="select" value={form.driver_id} onChange={(e) => setForm({ ...form, driver_id: e.target.value })}><option value="">Unassigned</option>{data.drivers.filter((d: any) => !d.vehicle_id || d.vehicle_id === selectedVehicle?.id).map((d: any) => <option key={d.id} value={d.id}>{d.name} ({d.phone})</option>)}</select></div>
                </div>
              )}

              {modal === 'route' && (
                <div className="grid-2">
                  <FormField label="Route Code *" value={form.route_code} onChange={(v) => setForm({ ...form, route_code: v })} />
                  <FormField label="Route Name *" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
                  <div className="form-row"><label>Vehicle *</label><select className="select" value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}><option value="">Select Vehicle</option>{data.vehicles.filter((v: any) => !data.routes.some((r: any) => r.status !== 'INACTIVE' && r.vehicle_no === v.vehicle_number)).map((v: any) => <option key={v.id} value={v.vehicle_number}>{v.vehicle_number}</option>)}</select></div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <FormField label="Description" value={form.status} onChange={(v) => setForm({ ...form, status: v })} />
                  </div>
                </div>
              )}

              {modal === 'stop' && (
                <div className="grid-2">
                  <FormField label="Stop Name *" value={form.stop_name} onChange={(v) => setForm({ ...form, stop_name: v })} />
                  <FormField label="Sequence *" type="number" value={selectedStop ? form.sequence : ((selectedRoute?.stops || []).filter((s: any) => s.status !== 'INACTIVE').length + 1)} onChange={(v) => setForm({ ...form, sequence: v })} />
                  <FormField label="Address" value={form.stop_address} onChange={(v) => setForm({ ...form, stop_address: v })} />
                  <FormField label="Pickup Time" value={form.pickup_time} onChange={(v) => setForm({ ...form, pickup_time: v })} />
                  <FormField label="Drop Time" value={form.drop_time} onChange={(v) => setForm({ ...form, drop_time: v })} />
                </div>
              )}

              {modal === 'student-assign' && (
                <div className="grid-2">
                  <div className="form-row"><label>Student *</label><input className="inp" placeholder="Search student..." value={allocationStudentSearch} onChange={(e) => setAllocationStudentSearch(e.target.value)} /><select className="select" value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })}><option value="">Select Student</option>{data.students?.filter((s: any) => `${s.name} ${s.roll_no} ${s.id}`.toLowerCase().includes(allocationStudentSearch.trim().toLowerCase())).map((s: any) => <option key={s.id} value={s.id}>{s.name} ({s.roll_no})</option>)}</select></div>
                  {!studentAssignVehicleId && <div className="form-row"><label>Route *</label><select className="select" value={form.route_id} onChange={(e) => setForm({ ...form, route_id: e.target.value, pickup_stop_id: '', drop_stop_id: '' })}>
                    <option value="">Select Route</option>{data.routes.map((r: any) => <option key={r.id} value={r.id}>{r.route_code} - {r.name}</option>)}</select></div>
                  }
                  <div className="form-row"><label>Stop *</label><select className="select" value={form.pickup_stop_id} onChange={(e) => {
                    const stopId = e.target.value
                    setForm({ ...form, pickup_stop_id: stopId, drop_stop_id: stopId })
                  }}>
                    <option value="">Select Stop</option>{data.routes.find((r: any) => r.id === form.route_id)?.stops?.map((s: any) => <option key={s.id} value={s.id}>{s.sequence}. {s.name}</option>)}</select></div>
                  <div className="form-row"><label>Vehicle *</label><select className="select" value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}>
                    <option value="">Select Vehicle</option>{data.vehicles.map((v: any) => <option key={v.id} value={v.id}>{v.vehicle_number} ({Math.max(0, v.capacity - v.occupied)} available)</option>)}</select></div>
                  {!studentAssignVehicleId && <div className="form-row"><label>Driver (Optional)</label><select className="select" value={form.driver_id} onChange={(e) => setForm({ ...form, driver_id: e.target.value })}>
                    <option value="">Unassigned</option>{data.drivers.map((d: any) => <option key={d.id} value={d.id}>{d.name} ({d.employee_id})</option>)}</select></div>
                  }
                </div>
              )}
            </div>

            <div className="modal-f">
              <button className="btn btn-out" onClick={closeModal}>Cancel</button>
              <button className="btn btn-crimson" onClick={handleSave} disabled={loading}>
                {loading ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function DriverDashboard() {
  const [data, setData] = useState<any>(null)
  const [trip, setTrip] = useState<any>(null)
  const [direction, setDirection] = useState('PICKUP')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    api.transportDriverDashboard().then(setData).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!trip || !data?.vehicle) return
    const id = navigator.geolocation?.watchPosition((p) => {
      api.sendTransportLocation({
        vehicle_id: data.vehicle.id,
        trip_id: trip.id,
        latitude: p.coords.latitude,
        longitude: p.coords.longitude,
      }).catch((e) => setError(`GPS update failed: ${e.message || 'Network error'}`))
    }, (e) => setError(`GPS unavailable: ${e.message}`), { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 })
    return () => {
      if (id != null) navigator.geolocation.clearWatch(id)
    }
  }, [trip, data])

  if (!data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead
        title={`Welcome, ${data.driver?.name || 'Driver'}`}
        sub="Assigned vehicle, route, and student information"
      />

      {error && <div className="notice rose">{error}</div>}
      {success && <div className="notice" style={{ background: '#e4f5ef', borderColor: '#16a34a', color: '#15803d' }}>{success}</div>}

      <Kpis
        items={[
          { label: 'Vehicle', value: data.vehicle?.vehicle_number || 'ï¿½' },
          { label: 'Capacity', value: data.vehicle?.capacity || 'ï¿½' },
          { label: 'Route', value: data.route?.name || 'ï¿½' },
          { label: 'Students', value: data.students?.length || 0 },
        ]}
      />

      <Section title="Route Stops">
        {data.route?.stops && data.route.stops.length > 0 ? (
          <div className="card">
            <div className="card-pad">
              {data.route.stops.map((s: any) => (
                <div className="list-row" key={s.id}>
                  <b>{s.sequence}. {s.name}</b>
                  <span>{s.pickup_time || 'ï¿½'}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState text="No route assigned" />
        )}
      </Section>

      <Section title="Assigned Students">
        {data.students && data.students.length > 0 ? (
          <div className="card">
            <div className="card-pad">
              {data.students.map((s: any, i: number) => (
                <div key={i} style={{ paddingBottom: 12, borderBottom: i < data.students.length - 1 ? '1px solid var(--line-2)' : 'none' }}>
                  <p style={{ marginBottom: 4 }}><b>{s.student_name}</b></p>
                  <p className="hint">{s.student_id}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState text="No students assigned" />
        )}
      </Section>

      <Section title="Trip Control">
        <div className="card">
          <div className="card-pad">
            {trip ? (
              <>
                <div style={{ padding: '12px 14px', background: '#fbe9e7', borderRadius: 9, marginBottom: 16, color: '#c73532' }}>
                  <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>?? TRIP RUNNING</p>
                  <p style={{ fontSize: 13, marginBottom: 4 }}>{data.route?.name} ï¿½ {trip.trip_type}</p>
                  <p className="hint">GPS tracking is active</p>
                </div>
                <button
                  className="btn btn-rose"
                  onClick={() => {
                    api.endTransportTrip(trip.id).then(() => {
                      setTrip(null)
                      setSuccess('Trip ended')
                    })
                  }}
                  style={{ width: '100%' }}
                >
                  End Trip
                </button>
              </>
            ) : (
              <>
                <p style={{ marginBottom: 12, fontSize: 13, color: 'var(--txt-mute)' }}>Select trip type and start</p>
                <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
                  <button
                    className={direction === 'PICKUP' ? 'btn btn-crimson' : 'btn btn-out'}
                    onClick={() => setDirection('PICKUP')}
                  >
                    Pickup
                  </button>
                  <button
                    className={direction === 'DROP' ? 'btn btn-crimson' : 'btn btn-out'}
                    onClick={() => setDirection('DROP')}
                  >
                    Drop
                  </button>
                </div>
                <button
                  className="btn btn-crimson"
                  onClick={() => {
                    api.startTransportTrip({
                      vehicle_id: data.vehicle.id,
                      driver_id: data.driver_id || data.driver?.id,
                      trip_type: direction,
                    })
                      .then((x: any) => {
                        setTrip(x)
                        setSuccess(`${direction} trip started`)
                      })
                      .catch((e) => setError(e.message))
                  }}
                  style={{ width: '100%' }}
                >
                  Start {direction} Trip
                </button>
              </>
            )}
          </div>
        </div>
      </Section>
    </div>
  )
}

function Section({ title, action, children }: any) {
  return (
    <section style={{ marginTop: 24 }}>
      <div className="card-h">
        <h3>{title}</h3>
        {action}
      </div>
      {children}
    </section>
  )
}

function FormField({ label, value, onChange, type = 'text' }: any) {
  return (
    <div className="form-row">
      <label>{label}</label>
      <input
        className="inp"
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}

function EmptyState({ text }: any) {
  return (
    <div className="card">
      <div className="card-pad">
        <Empty text={text} />
      </div>
    </div>
  )
}

function RequestsTable({ rows, routes, onApprove }: any) {
  return (
    <div className="card">
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>Student</th>
              <th>ID</th>
              <th>Route</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any) => (
              <tr key={r.id}>
                <td><b>{r.student_name}</b></td>
                <td className="mono">{r.student_id}</td>
                <td>{routes.find((x: any) => x.id === r.route_id)?.name || r.route_id}</td>
                <td><Pill s={r.status} /></td>
                <td>
                  {r.status === 'PENDING' && (
                    <button className="btn btn-sm btn-crimson" onClick={() => onApprove(r)}>
                      Approve
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function OccupancyCards({ vehicles, emptyText = 'No vehicles added' }: any) {
  if (!vehicles.length) {
    return <div className="card"><div className="card-pad"><Empty text={emptyText} /></div></div>
  }

  return (
    <div className="grid-2">
      {vehicles.map((v: any) => (
        <div className="card" key={v.id}>
          <div className="card-h">
            <h4 style={{ fontSize: 16, marginBottom: 0 }}>{v.vehicle_number}</h4>
            <Pill s={v.status} />
          </div>
          <div className="card-pad">
            <div className="snap">
              <b>Type</b>
              <span>{v.vehicle_type}</span>
            </div>
            <div className="snap">
              <b>Occupied</b>
              <span>{v.occupied}/{v.capacity}</span>
            </div>
            <div className="snap">
              <b>Available</b>
              <span>{Math.max(0, v.capacity - v.occupied)}</span>
            </div>
            <div className="fill-bar">
              <span style={{ width: `${Math.min(100, v.capacity ? (v.occupied / v.capacity) * 100 : 0)}%` }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function RequestApprovalForm({ request, routes, vehicles, drivers, onApprove, onReject }: any) {
  const [form, setForm] = useState({
    route_id: request.route_id,
    pickup_stop_id: request.pickup_stop_id || '',
    drop_stop_id: request.drop_stop_id || request.pickup_stop_id || '',
    vehicle_id: '',
    driver_id: '',
  })
  const [error, setError] = useState('')

  const route = routes.find((x: any) => x.id === form.route_id)

  return (
    <div>
      {error && (
        <div className="notice rose" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}
      <p style={{ marginBottom: 16, fontSize: 13 }}>
        <b>{request.student_name}</b> is requesting transport
      </p>

      <div className="grid-2">
        <div className="form-row">
          <label>Route</label>
          <select className="select" value={form.route_id} onChange={(e) => setForm({ ...form, route_id: e.target.value, pickup_stop_id: '', drop_stop_id: '' })}>
            <option value="">Select Route</option>
            {routes.map((r: any) => (
              <option key={r.id} value={r.id}>
                {r.route_code} - {r.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-row" style={{ gridColumn: '1 / -1' }}>
          <label>Stop</label>
          <select className="select" value={form.pickup_stop_id} onChange={(e) => {
            const stopId = e.target.value
            setForm({ ...form, pickup_stop_id: stopId, drop_stop_id: stopId })
          }}>
            <option value="">Select Stop</option>
            {route?.stops?.map((s: any) => (
              <option key={s.id} value={s.id}>
                {s.sequence}. {s.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label>Vehicle</label>
          <select className="select" value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}>
            <option value="">Select Vehicle</option>
            {vehicles.map((v: any) => (
              <option key={v.id} value={v.id}>
                {v.vehicle_number} ({v.capacity - v.occupied} seats available)
              </option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label>Driver</label>
          <select className="select" value={form.driver_id} onChange={(e) => setForm({ ...form, driver_id: e.target.value })}>
            <option value="">Select Driver</option>
            {drivers.map((d: any) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.employee_id})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
        <button className="btn btn-out" onClick={onReject}>
          Reject
        </button>
        <button className="btn btn-crimson" onClick={() => {
          const stopId = form.pickup_stop_id || form.drop_stop_id
          if (!stopId) {
            setError('Please select the stop for this student assignment.')
            return
          }
          setError('')
          onApprove({
            student_id: request.student_id,
            route_id: form.route_id,
            pickup_stop_id: stopId,
            drop_stop_id: stopId,
            vehicle_id: form.vehicle_id,
            driver_id: form.driver_id,
          })
        }}>
          Approve & Assign
        </button>
      </div>
    </div>
  )
}
