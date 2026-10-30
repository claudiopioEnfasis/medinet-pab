import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { API, checkAvailability, setToken, setUnauthorizedHandler } from './api.js';
import { Empty, fmtDate, fmtTime, Icon, initialDates, Modal, ROOM_STATUS, StatusPill, SURGERY_STATUS } from './ui.jsx';

const MENU = [
  { id: 'dashboard', label: 'Vista general', icon: 'grid' },
  { id: 'surgeries', label: 'Programación', icon: 'calendar' },
  { id: 'data', label: 'Pacientes y equipo', icon: 'users' },
];

function Stat({ icon, value, title, description, tone = 'mint' }) {
  return <div className="stat-card">
    <div className={`stat-icon icon-${tone}`}><Icon name={icon} size={22}/></div>
    <strong className="stat-value">{value}</strong>
    <span className="stat-title">{title}</span>
    <span className="stat-note">{description}</span>
  </div>;
}

const STAGES = [
  { id: 'available', label: 'Disponibles', tone: 'ready' },
  { id: 'occupied', label: 'En uso', tone: 'busy' },
  { id: 'sanitizing', label: 'Sanitización', tone: 'clean' },
  { id: 'maintenance', label: 'Mantención', tone: 'repair' },
];

function OperationsPulse({ rooms, surgeries }) {
  const counts = Object.fromEntries(STAGES.map(s => [s.id, rooms.filter(r => r.status === s.id).length]));
  const today = new Date().toDateString();
  const todaySurgeries = surgeries.filter(s => new Date(s.starts_at).toDateString() === today && s.status !== 'cancelled');
  return <section className="ops-pulse" aria-label="Resumen operativo">
    <div className="pulse-head"><div><span className="pulse-index">01 / MONITOREO</span><h2>Pulso del centro quirúrgico</h2><p>Distribución actual de los pabellones y actividad del día.</p></div>
      <div className="pulse-today"><span>Intervenciones de hoy</span><strong>{String(todaySurgeries.length).padStart(2, '0')}</strong></div></div>
    <div className="capacity-track" role="img" aria-label={STAGES.map(x => `${x.label}: ${counts[x.id]}`).join(', ')}>
      {rooms.map(room => <span key={room.id} className={`capacity-segment seg-${STAGES.find(s => s.id === room.status)?.tone || 'repair'}`} title={`${room.name}: ${ROOM_STATUS[room.status]?.label || room.status}`}/>)}
      {rooms.length === 0 && <span className="capacity-segment seg-empty"/>}
    </div>
    <div className="capacity-legend">{STAGES.map(st => <div className="legend-item" key={st.id}><i className={`legend-dot seg-${st.tone}`}/><span>{st.label}</span><strong>{counts[st.id]}</strong></div>)}</div>
  </section>;
}

function RoomCard({ room, onStatus, onSchedule, pending, editable }) {
  return <article className={`room-card room-${room.status}`}>
    <div className="room-top"><span className="room-avatar"><Icon name="building" size={22}/></span><StatusPill status={room.status}/></div>
    <span className="room-code">{room.code}</span>
    <h3>{room.name}</h3>
    <div className="room-illustration" aria-hidden="true"><div className="room-schematic"><span className="schematic-bed"/><span className="schematic-lamp"/><span className="schematic-side"/></div><span className="room-illustration-caption">QUIRÓFANO / {room.code}</span></div><div className="room-divider"/>
    <label className="small-label" htmlFor={`status-${room.id}`}>Estado del pabellón</label>
    <select id={`status-${room.id}`} disabled={pending || !editable} className="select room-select" value={room.status} onChange={e => onStatus(room.id, e.target.value)}>
      {Object.entries(ROOM_STATUS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}
    </select>
    {editable && <button className="text-action" type="button" onClick={() => onSchedule(room.id)}><Icon name="plus" size={15}/> Programar cirugía</button>}
  </article>;
}

function SurgeryRow({ surgery, lookup, onChangeStatus, pending, editable }) {
  const room = lookup.rooms[surgery.room_id];
  const patient = lookup.patients[surgery.patient_id];
  const medics = surgery.staff_ids.map(id => lookup.staff[id]?.full_name || `Profesional #${id}`).join(', ');
  return <div className="surgery-row">
    <div className="row-time"><strong>{fmtTime(surgery.starts_at)}</strong><span>{fmtDate(surgery.starts_at, false)}</span><small>Hasta {fmtTime(surgery.ends_at)}</small></div>
    <div className="row-content"><strong>{surgery.procedure}</strong><span>{patient?.full_name || `Paciente #${surgery.patient_id}`} · {room?.name || `Pabellón #${surgery.room_id}`}</span><small title={medics}>{medics}</small></div>
    <div className="row-state"><StatusPill status={surgery.status} domain="surgery"/><span className={`urgency ${surgery.urgency === 'emergency' ? 'urgent' : ''}`}>{surgery.urgency === 'emergency' ? 'Urgencia' : 'Electiva'}</span></div>
    <div className="row-actions">
      {editable && surgery.status === 'scheduled' && <><button disabled={pending} className="button tiny secondary" onClick={() => onChangeStatus(surgery.id, 'in_progress')}>Iniciar</button><button disabled={pending} className="button tiny subtle" onClick={() => onChangeStatus(surgery.id, 'cancelled')}>Cancelar</button></>}
      {editable && surgery.status === 'in_progress' && <button disabled={pending} className="button tiny secondary" onClick={() => onChangeStatus(surgery.id, 'completed')}>Finalizar</button>}
    </div>
  </div>;
}

function localDayKey(value) {
  const date = new Date(value);
  const pad = n => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function MonthCalendar({ surgeries, selectedDay, onSelect }) {
  const [offset, setOffset] = useState(0);
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const y = monthStart.getFullYear(); const m = monthStart.getMonth();
  const before = (monthStart.getDay() + 6) % 7;
  const last = new Date(y, m + 1, 0).getDate();
  const numCells = Math.ceil((before + last) / 7) * 7;
  const counts = {};
  surgeries.filter(s => s.status !== 'cancelled').forEach(s => {
    const key = localDayKey(s.starts_at);
    counts[key] = (counts[key] || 0) + 1;
  });
  const days = Array.from({ length: numCells }, (_, index) => {
    const day = new Date(y, m, index + 1 - before);
    const key = localDayKey(day);
    return { key, number: day.getDate(), current: day.getMonth() === m, count: counts[key] || 0, today: key === localDayKey(now) };
  });
  return <div className="calendar-panel">
    <div className="calendar-heading"><div><h2>Calendario quirúrgico</h2><p>Selecciona un día para filtrar las intervenciones.</p></div>
      <div className="calendar-tools"><button className="icon-button" type="button" aria-label="Mes anterior" onClick={() => setOffset(o => o - 1)}><Icon name="arrow" className="flip" size={18}/></button><strong>{new Intl.DateTimeFormat('es-CL', { month: 'long', year: 'numeric' }).format(monthStart)}</strong><button className="icon-button" type="button" aria-label="Mes siguiente" onClick={() => setOffset(o => o + 1)}><Icon name="arrow" size={18}/></button></div>
    </div>
    <div className="calendar-grid" role="group" aria-label="Días del mes">
      {['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'].map(d => <div key={d} className="calendar-weekday">{d}</div>)}
      {days.map(day => <button key={day.key} type="button" className={`calendar-day ${!day.current ? 'calendar-outside' : ''} ${day.today ? 'calendar-today' : ''} ${selectedDay === day.key ? 'calendar-selected' : ''}`} onClick={() => onSelect(selectedDay === day.key ? null : day.key)} aria-label={`${fmtDate(day.key + 'T12:00:00', false)}, ${day.count} cirugías`}>
        <span>{day.number}</span>{day.count > 0 && <small>{day.count} {day.count === 1 ? 'cirugía' : 'cirugías'}</small>}</button>)}
    </div>
  </div>;
}

function SurgeryForm({ rooms, patients, staff, presetRoom, onClose, onCreated }) {
  const availableRoom = rooms.find(room => room.status === 'available');
  const [fields, setFields] = useState(() => ({
    room_id: presetRoom || availableRoom?.id || rooms[0]?.id || '',
    patient_id: patients[0]?.id || '',
    staff_ids: staff.length ? [staff[0].id] : [],
    procedure: '', urgency: 'elective', ...initialDates(),
  }));
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [availability, setAvailability] = useState(null);
  const [error, setError] = useState('');

  const change = (key, value) => { setFields(current => ({ ...current, [key]: value })); setAvailability(null); setError(''); };
  const toggleStaff = id => change('staff_ids', fields.staff_ids.includes(id) ? fields.staff_ids.filter(item => item !== id) : [...fields.staff_ids, id]);
  const payload = () => {
    if (!fields.room_id || !fields.patient_id || !fields.staff_ids.length) throw new Error('Selecciona quirófano, paciente y al menos un profesional.');
    if (!fields.procedure.trim()) throw new Error('Indica el nombre del procedimiento.');
    if (!fields.starts_at || !fields.ends_at) throw new Error('Indica las fechas y horas de inicio y término.');
    const starts_at = new Date(fields.starts_at), ends_at = new Date(fields.ends_at);
    if (Number.isNaN(starts_at.getTime()) || Number.isNaN(ends_at.getTime()) || starts_at >= ends_at) throw new Error('La fecha de término debe ser posterior a la de inicio.');
    return {
      room_id: Number(fields.room_id), patient_id: Number(fields.patient_id),
      staff_ids: fields.staff_ids.map(Number), procedure: fields.procedure.trim(), urgency: fields.urgency,
      starts_at: starts_at.toISOString(), ends_at: ends_at.toISOString(),
    };
  };

  async function verify() {
    setError(''); setAvailability(null); setChecking(true);
    try { const data = payload(); setAvailability(await checkAvailability(data)); }
    catch (err) { setError(err.message); }
    finally { setChecking(false); }
  }
  async function submit(event) {
    event.preventDefault(); setError(''); setSaving(true);
    try { await API.createSurgery(payload()); await onCreated(); }
    catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  return <Modal wide title="Programar cirugía" subtitle="El sistema comprobará la disponibilidad del quirófano, paciente y equipo médico." onClose={onClose}>
    <form onSubmit={submit} className="form-stack">
      <div className="form-grid">
        <label className="field">Pabellón<select className="select" required value={fields.room_id} onChange={e => change('room_id', Number(e.target.value))}>
          <option value="" disabled>Seleccionar pabellón</option>
          {rooms.map(room => <option key={room.id} value={room.id}>{room.name} — {ROOM_STATUS[room.status]?.label}</option>)}
        </select></label>
        <label className="field">Paciente<select className="select" required value={fields.patient_id} onChange={e => change('patient_id', Number(e.target.value))}>
          <option value="" disabled>Seleccionar paciente</option>
          {patients.map(patient => <option key={patient.id} value={patient.id}>{patient.full_name}</option>)}
        </select></label>
        <label className="field field-full">Procedimiento<input required minLength={3} maxLength={200} placeholder="Ej. Apendicectomía (demostración)" value={fields.procedure} onChange={e => change('procedure', e.target.value)}/></label>
        <label className="field">Tipo de cirugía<select className="select" value={fields.urgency} onChange={e => change('urgency', e.target.value)}><option value="elective">Electiva</option><option value="emergency">Urgencia</option></select></label>
        <div className="field"><span>Profesionales asignados</span><div className="staff-checks">{staff.length ? staff.map(person => <label key={person.id} className="staff-check"><input type="checkbox" checked={fields.staff_ids.includes(person.id)} onChange={() => toggleStaff(person.id)}/><span>{person.full_name}<small>{person.specialty}</small></span></label>) : <p className="muted">Primero registra un profesional.</p>}</div></div>
        <label className="field">Inicio<input required type="datetime-local" value={fields.starts_at} onChange={e => change('starts_at', e.target.value)}/></label>
        <label className="field">Término<input required type="datetime-local" value={fields.ends_at} onChange={e => change('ends_at', e.target.value)}/></label>
      </div>
      {availability && <div className={`callout ${availability.available ? 'callout-success' : 'callout-danger'}`} role="status"><Icon name={availability.available ? 'check' : 'alert'} size={18}/><div><strong>{availability.available ? 'Horario disponible' : 'Se detectaron conflictos'}</strong>{!availability.available && availability.conflicts.map((conflict, index) => <p key={index}>{conflict}</p>)}</div></div>}
      {error && <div className="callout callout-danger" role="alert"><Icon name="alert" size={18}/>{error}</div>}
      <div className="form-actions"><button type="button" className="button secondary" onClick={verify} disabled={saving || checking}>{checking ? 'Comprobando…' : 'Verificar disponibilidad'}</button><span className="grow"/><button type="button" className="button subtle" onClick={onClose}>Cerrar</button><button type="submit" className="button primary" disabled={saving || checking || !rooms.length || !patients.length || !staff.length}>{saving ? 'Guardando…' : 'Guardar cirugía'}</button></div>
    </form>
  </Modal>;
}

const modalContent = {
  room: { title: 'Registrar pabellón', subtitle: 'Nuevo quirófano dentro de MediNet PAB.', fields: [{ key: 'code', label: 'Código', hint: 'Ej. PAB-03', maxLength: 24 }, { key: 'name', label: 'Nombre', hint: 'Ej. Pabellón 3', maxLength: 100 }] },
  patient: { title: 'Paciente de demostración', subtitle: 'Usar exclusivamente identidades ficticias.', fields: [{ key: 'reference', label: 'Referencia', hint: 'Ej. DEMO-P03', maxLength: 32 }, { key: 'full_name', label: 'Nombre ficticio', hint: 'Ej. Paciente Demo Tres', maxLength: 120 }] },
  staff: { title: 'Profesional de demostración', subtitle: 'Integración con el módulo MED pendiente.', fields: [{ key: 'reference', label: 'Referencia', hint: 'Ej. DEMO-M03', maxLength: 32 }, { key: 'full_name', label: 'Nombre ficticio', hint: 'Ej. Dr. Ejemplo Tres', maxLength: 120 }, { key: 'specialty', label: 'Especialidad', hint: 'Ej. Traumatología', maxLength: 100 }] },
};
function SimpleForm({ kind, onClose, onCreated }) {
  const config = modalContent[kind];
  const [fields, setFields] = useState({}); const [saving, setSaving] = useState(false); const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); setSaving(true); setError('');
    try {
      const data = Object.fromEntries(config.fields.map(f => [f.key, (fields[f.key] || '').trim()]));
      await ({ room: API.createRoom, patient: API.createPatient, staff: API.createStaff })[kind](data);
      await onCreated();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }
  return <Modal title={config.title} subtitle={config.subtitle} onClose={onClose}><form className="form-stack" onSubmit={submit}>
    {config.fields.map(field => <label className="field" key={field.key}>{field.label}<input required maxLength={field.maxLength} minLength={field.key === 'code' || field.key === 'reference' ? 2 : 3} placeholder={field.hint} value={fields[field.key] || ''} onChange={e => setFields({ ...fields, [field.key]: e.target.value })}/></label>)}
    {error && <div className="callout callout-danger" role="alert"><Icon name="alert" size={18}/>{error}</div>}
    <div className="form-actions"><button type="button" className="button subtle" onClick={onClose}>Cancelar</button><button type="submit" className="button primary" disabled={saving}>{saving ? 'Guardando…' : 'Registrar'}</button></div>
  </form></Modal>;
}

function LoginScreen({ onAuthenticated }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      const result = await API.login({ username: username.trim().toLowerCase(), password });
      setToken(result.access_token);
      const user = await API.me();
      onAuthenticated(user);
    } catch (err) {
      setToken(null); setError(err.message);
    } finally { setBusy(false); }
  }
  return <div className="auth-shell">
    <section className="auth-info">
      <div className="auth-logo"><Icon name="heart" size={27}/> MediNet<span>Core</span></div>
      <div><div className="auth-eyebrow">MEDINET / SURGICAL SUITE</div><h1>Precisión en cada <em>intervención.</em></h1><p>Un espacio de trabajo para coordinar quirófanos, profesionales y cirugías con claridad y seguridad.</p><div className="auth-graphic" aria-hidden="true"><span className="orbit orbit-one"/><span className="orbit orbit-two"/><span className="orbit orbit-three"/><span className="orbit-center"><Icon name="activity" size={43}/></span><span className="orbit-star orbit-star-a"/><span className="orbit-star orbit-star-b"/></div></div>
      <div className="auth-foot">Prototipo académico · Información ficticia · v0.5</div>
    </section>
    <section className="auth-panel"><div className="auth-card">
      <div className="auth-lock"><Icon name="shield" size={24}/></div>
      <h2>Iniciar sesión</h2><p className="auth-subtitle">Ingresa con un usuario creado por el administrador del proyecto.</p>
      <form onSubmit={submit} className="form-stack">
        <label className="field">Usuario<input autoComplete="username" required minLength={3} maxLength={40} value={username} onChange={e => setUsername(e.target.value)} placeholder="Ej. admin"/></label>
        <label className="field">Contraseña<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} placeholder="Tu contraseña"/></label>
        {error && <div className="callout callout-danger" role="alert"><Icon name="alert" size={18}/>{error}</div>}
        <button disabled={busy} className="button primary auth-submit" type="submit">{busy ? 'Validando…' : 'Entrar al sistema'}</button>
      </form><p className="auth-tip">La sesión dura 30 minutos y no se almacena en el navegador. Se solicita nuevamente al actualizar la página.</p>
    </div></section>
  </div>;
}

export default function App() {
  const [session, setSession] = useState(null);
  useEffect(() => {
    setUnauthorizedHandler(() => { setToken(null); setSession(null); });
    return () => setUnauthorizedHandler(null);
  }, []);
  const logout = () => { setToken(null); setSession(null); };
  return session
    ? <Workspace key={session.id} session={session} onLogout={logout}/>
    : <LoginScreen onAuthenticated={setSession}/>;
}

function Workspace({ session, onLogout }) {
  const canEdit = session.role === 'admin' || session.role === 'coordinator';
  const isAdmin = session.role === 'admin';
  const [page, setPage] = useState('dashboard');
  const [data, setData] = useState({ rooms: [], patients: [], staff: [], surgeries: [] });
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState('');
  const [pending, setPending] = useState(false);
  const [modal, setModal] = useState(null);
  const [presetRoom, setPresetRoom] = useState(null);
  const [toast, setToast] = useState(null);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedDay, setSelectedDay] = useState(null);

  const reload = useCallback(async () => {
    try {
      const [rooms, patients, staff, surgeries] = await Promise.all([API.rooms(), API.patients(), API.staff(), API.surgeries()]);
      setData({ rooms, patients, staff, surgeries }); setConnectionError('');
    } catch (err) { setConnectionError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { reload(); const t = setInterval(reload, 30000); return () => clearInterval(t); }, [reload]);
  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(() => setToast(null), 5500);
    return () => clearTimeout(t);
  }, [toast]);

  const lookup = useMemo(() => ({
    rooms: Object.fromEntries(data.rooms.map(row => [row.id, row])),
    patients: Object.fromEntries(data.patients.map(row => [row.id, row])),
    staff: Object.fromEntries(data.staff.map(row => [row.id, row])),
  }), [data]);
  const active = data.surgeries.filter(item => item.status === 'scheduled' || item.status === 'in_progress');
  const upcoming = active.filter(item => new Date(item.ends_at).getTime() >= Date.now()).slice(0, 5);
  const filtered = data.surgeries.filter(item => {
    const statusMatch = filter === 'all' || item.status === filter;
    const value = `${item.procedure} ${lookup.rooms[item.room_id]?.name || ''} ${lookup.patients[item.patient_id]?.full_name || ''}`.toLocaleLowerCase('es');
    return statusMatch && (!selectedDay || localDayKey(item.starts_at) === selectedDay) && value.includes(search.toLocaleLowerCase('es'));
  }).sort((a, b) => new Date(b.starts_at) - new Date(a.starts_at));

  function open(kind, roomId = null) { setPresetRoom(roomId); setModal(kind); }
  const showToast = (message, type = 'success') => setToast({ message, type });
  async function changeStatus(action, message) {
    setPending(true);
    try { await action(); await reload(); showToast(message); }
    catch (err) { showToast(err.message, 'error'); }
    finally { setPending(false); }
  }
  async function created(message) { await reload(); setModal(null); showToast(message); }
  function navigate(id) { setPage(id); setModal(null); }

  return <div className="layout">
    <aside className="sidebar">
      <div className="brand"><div className="brand-symbol"><Icon name="heart" size={24}/></div><div><strong>MediNet<span>Core</span></strong><small>MÓDULO 06 / PAB</small></div></div>
      <div className="sidebar-caption">GESTIÓN HOSPITALARIA</div>
      <nav className="menu" aria-label="Navegación principal">{MENU.map(item => <button key={item.id} className={`menu-item ${page === item.id ? 'menu-active' : ''}`} type="button" onClick={() => navigate(item.id)}><Icon name={item.icon} size={19}/>{item.label}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sandbox-label"><Icon name="shield" size={18}/><div><strong>Entorno académico</strong><small>Sin datos clínicos reales</small></div></div><div className="side-footer">EVA 02 · Desarrollo Seguro<br/>MediNet-Core · v0.5</div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="mobile-brand"><Icon name="heart" size={20}/> MediNet <b>PAB</b></div><div className="breadcrumb">Plataforma hospitalaria <Icon name="arrow" size={14}/> <strong>{MENU.find(x => x.id === page)?.label}</strong></div><div className="topbar-right"><span className={`api-indicator ${connectionError ? 'api-off' : ''}`}><i/>{connectionError ? 'API sin conexión' : 'API conectada'}</span><button className="icon-button" onClick={reload} title="Actualizar datos" aria-label="Actualizar datos"><Icon name="refresh" size={19}/></button><span className="session-user" title={`Rol: ${session.role}`}>{session.username} · {session.role}</span><button type="button" className="button secondary tiny" onClick={onLogout}>Salir</button><span className="avatar">{session.username.slice(0, 2).toUpperCase()}</span></div></header>
      <main className="main">
        {connectionError && <div className="connection-banner" role="alert"><Icon name="alert" size={19}/><div><strong>Problema de conexión con el backend</strong><p>{connectionError}</p></div><button className="button secondary tiny" onClick={reload}>Reintentar</button></div>}
        {loading ? <div className="loading"><span className="spinner"/> Conectando con MediNet PAB…</div> : <>
          {page === 'dashboard' && <>
            <section className="hero-command">
              <div className="hero-content"><div className="hero-overline"><span className="hero-live"/> CENTRO DE CONTROL / PAB.06</div>
                <h1>La operación, <em>bajo control.</em></h1><p>Una vista precisa de tu agenda quirúrgica, la disponibilidad y el equipo operativo.</p>
                <div className="hero-buttons">{canEdit && <button className="button hero-primary" onClick={() => open('surgery')}><Icon name="plus" size={18}/> Programar cirugía</button>}
                <button className="button hero-ghost" onClick={() => navigate('surgeries')}><Icon name="calendar" size={17}/> Ver agenda <Icon name="arrow" size={15}/></button></div>
              </div>
              <div className="hero-signal" aria-hidden="true"><div className="signal-ring signal-ring-a"/><div className="signal-ring signal-ring-b"/><div className="signal-ring signal-ring-c"/><div className="signal-core"><Icon name="activity" size={42}/></div><span className="signal-tag signal-tag-one">PAB / LIVE</span><span className="signal-tag signal-tag-two">SISTEMA / 06</span></div>
            </section>
            <div className="stats-grid"><Stat icon="building" value={data.rooms.length} title="Pabellones" description="Total registrados"/><Stat icon="check" tone="mint" value={data.rooms.filter(x => x.status === 'available').length} title="Disponibles" description="Listos para operar"/><Stat icon="activity" tone="orange" value={data.rooms.filter(x => x.status === 'occupied').length} title="En uso" description="Intervención en proceso"/><Stat icon="calendar" tone="blue" value={active.filter(x => x.status === 'scheduled').length} title="Cirugías programadas" description="Pendientes de inicio"/></div>
            <OperationsPulse rooms={data.rooms} surgeries={data.surgeries}/><section className="section"><div className="section-header"><div><h2>Estado de quirófanos</h2><p>Actualiza los estados y verifica la disponibilidad.</p></div>{isAdmin && <button className="button secondary" onClick={() => open('room')}><Icon name="plus" size={17}/> Agregar pabellón</button>}</div>
              {data.rooms.length ? <div className="room-grid">{data.rooms.map(room => <RoomCard key={room.id} room={room} pending={pending} editable={canEdit} onStatus={(id, status) => changeStatus(() => API.roomStatus(id, status), 'Estado del pabellón actualizado.')} onSchedule={id => open('surgery', id)}/>)}</div> : <Empty title="Aún no hay pabellones" text="Registra el primer pabellón o ejecuta el script de datos ficticios." icon="building"/>}
            </section>
            <section className="section"><div className="section-header"><div><h2>Próximas cirugías</h2><p>Intervenciones programadas o en proceso.</p></div><button className="link-button" onClick={() => navigate('surgeries')}>Ver todas <Icon name="arrow" size={16}/></button></div>
              <div className="list-panel">{upcoming.length ? upcoming.map(item => <SurgeryRow key={item.id} surgery={item} lookup={lookup} pending={pending} editable={canEdit} onChangeStatus={(id, status) => changeStatus(() => API.surgeryStatus(id, status), 'Estado de la cirugía actualizado.')}/>) : <Empty title="Sin intervenciones próximas" text="Programa una cirugía para visualizarla aquí."/>}</div>
            </section>
          </>}
          {page === 'surgeries' && <>
            <div className="page-heading"><div><div className="eyebrow">AGENDA / PLANIFICACIÓN</div><h1>Programación de cirugías</h1><p>Consulta procedimientos y controla su ejecución.</p></div>{canEdit && <button className="button primary" onClick={() => open('surgery')}><Icon name="plus" size={18}/> Programar cirugía</button>}</div>
            <MonthCalendar surgeries={data.surgeries} selectedDay={selectedDay} onSelect={setSelectedDay}/>
            {selectedDay && <div className="selected-day"><span>Mostrando cirugías del <strong>{fmtDate(selectedDay + 'T12:00:00', false)}</strong></span><button className="link-button" onClick={() => setSelectedDay(null)}>Ver todos los días <Icon name="close" size={16}/></button></div>}
            <div className="list-panel list-panel-pad"><div className="filters"><div className="searchbox"><Icon name="search" size={19}/><input aria-label="Buscar cirugía" placeholder="Buscar procedimiento o paciente…" value={search} onChange={e => setSearch(e.target.value)}/></div><select className="select filter-select" aria-label="Filtrar estado" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Todos los estados</option>{Object.entries(SURGERY_STATUS).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}</select></div>
              <div className="list-heading"><span>FECHA Y HORARIO</span><span>PROCEDIMIENTO</span><span>ESTADO</span><span>ACCIONES</span></div>{filtered.length ? filtered.map(item => <SurgeryRow key={item.id} surgery={item} lookup={lookup} pending={pending} editable={canEdit} onChangeStatus={(id, status) => changeStatus(() => API.surgeryStatus(id, status), 'Estado de la cirugía actualizado.')}/>) : <Empty title="No hay cirugías para mostrar" text="Crea una cirugía o modifica los filtros."/>}
            </div>
          </>}
          {page === 'data' && <>
            <div className="page-heading"><div><div className="eyebrow">DIRECTORIO / DEMOSTRACIÓN</div><h1>Pacientes y equipo médico</h1><p>Registros de ejemplo para probar las validaciones del módulo PAB.</p></div></div>
            <div className="demo-warning"><Icon name="info" size={20}/><span>Esta versión no está conectada a PAC ni MED. No ingreses nombres, RUN ni información médica real.</span></div>
            <div className="data-grid"><section className="data-card"><div className="section-header"><div><h2>Pacientes</h2><p>{data.patients.length} registros</p></div>{isAdmin && <button className="button secondary" onClick={() => open('patient')}><Icon name="plus" size={16}/> Agregar</button>}</div>{data.patients.length ? data.patients.map(person => <div className="person-row" key={person.id}><span className="person-icon"><Icon name="users" size={19}/></span><div><strong>{person.full_name}</strong><small>{person.reference}</small></div></div>) : <Empty title="Sin pacientes" text="Registra pacientes ficticios." icon="users"/>}</section>
              <section className="data-card"><div className="section-header"><div><h2>Equipo médico</h2><p>{data.staff.length} profesionales</p></div>{isAdmin && <button className="button secondary" onClick={() => open('staff')}><Icon name="plus" size={16}/> Agregar</button>}</div>{data.staff.length ? data.staff.map(person => <div className="person-row" key={person.id}><span className="person-icon medical"><Icon name="activity" size={19}/></span><div><strong>{person.full_name}</strong><small>{person.specialty} · {person.reference}</small></div></div>) : <Empty title="Sin profesionales" text="Registra profesionales ficticios." icon="users"/>}</section></div>
          </>}
          <footer className="footer">MediNet-Core / PAB · Módulo 6 · Proyecto académico de Desarrollo Seguro · <a href="/docs" target="_blank" rel="noopener noreferrer">Documentación Swagger</a></footer>
        </>}
      </main>
      <nav className="mobile-nav" aria-label="Navegación móvil">{MENU.map(item => <button key={item.id} type="button" className={page === item.id ? 'active' : ''} onClick={() => navigate(item.id)}><Icon name={item.icon} size={20}/><span>{item.label}</span></button>)}</nav>
    </div>
    {canEdit && modal === 'surgery' && <SurgeryForm rooms={data.rooms} patients={data.patients} staff={data.staff} presetRoom={presetRoom} onClose={() => setModal(null)} onCreated={() => created('Cirugía programada correctamente.')} />}
    {isAdmin && modal && modal !== 'surgery' && <SimpleForm kind={modal} onClose={() => setModal(null)} onCreated={() => created('Registro creado correctamente.')}/>}
    {toast && <div role={toast.type === 'error' ? 'alert' : 'status'} className={`toast ${toast.type === 'error' ? 'toast-danger' : ''}`}><Icon name={toast.type === 'error' ? 'alert' : 'check'} size={18}/><span>{toast.message}</span><button type="button" aria-label="Cerrar notificación" onClick={() => setToast(null)}><Icon name="close" size={16}/></button></div>}
  </div>;
}
