import React from 'react';

const p = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 10h18"/></>,
  users: <><circle cx="9" cy="8" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6m4 10v-2a6 6 0 0 0-4-5.7"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  arrow: <path d="m9 18 6-6-6-6"/>,
  activity: <path d="M3 12h4l3-7 4 14 3-7h4"/>,
  refresh: <><path d="M20 11a8 8 0 1 0-2 6"/><path d="M20 4v7h-7"/></>,
  shield: <><path d="M12 22c6-2 9-6 9-11V5l-9-3-9 3v6c0 5 3 9 9 11Z"/><path d="m9 12 2 2 4-4"/></>,
  close: <path d="M18 6 6 18M6 6l12 12"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 3"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  heart: <path d="M20.8 8.6c0 4-8.8 11.4-8.8 11.4S3.2 12.6 3.2 8.6a4.7 4.7 0 0 1 8.8-2.1 4.7 4.7 0 0 1 8.8 2.1Z"/>,
  arrowUp: <path d="M12 19V5m-7 7 7-7 7 7"/>,
  check: <path d="m5 12 5 5L20 7"/>,
  alert: <><path d="M12 3 2 21h20L12 3Z"/><path d="M12 9v4m0 4h.01"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></>,
  book: <><path d="M4 19V5a2 2 0 0 1 2-2h14v17H6a2 2 0 0 1 0-4h14"/></>,
  building: <><rect x="4" y="4" width="16" height="18" rx="2"/><path d="M9 4v18M4 10h16m-16 6h16"/></>,
};
export function Icon({ name, size = 20, className = '' }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{p[name] || p.grid}</svg>;
}

export const ROOM_STATUS = {
  available: { label: 'Disponible', tone: 'green' },
  occupied: { label: 'Ocupado', tone: 'red' },
  sanitizing: { label: 'Sanitización', tone: 'amber' },
  maintenance: { label: 'Mantención', tone: 'slate' },
};
export const SURGERY_STATUS = {
  scheduled: { label: 'Programada', tone: 'blue' },
  in_progress: { label: 'En proceso', tone: 'amber' },
  completed: { label: 'Finalizada', tone: 'green' },
  cancelled: { label: 'Cancelada', tone: 'slate' },
};
export function StatusPill({ status, domain = 'room' }) {
  const item = (domain === 'room' ? ROOM_STATUS : SURGERY_STATUS)[status] || { label: status, tone: 'slate' };
  return <span className={`pill pill-${item.tone}`}><span className="pill-dot" />{item.label}</span>;
}
export function fmtDate(input, withTime = true) {
  if (!input) return '—';
  const value = new Date(input);
  if (Number.isNaN(value.getTime())) return '—';
  return new Intl.DateTimeFormat('es-CL', withTime ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' } : { day: '2-digit', month: 'short', year: 'numeric' }).format(value);
}
export function fmtTime(input) {
  return input ? new Intl.DateTimeFormat('es-CL', { hour: '2-digit', minute: '2-digit' }).format(new Date(input)) : '—';
}
export function localInput(date) {
  const pad = n => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
export function initialDates() {
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(9, 0, 0, 0);
  const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
  return { starts_at: localInput(start), ends_at: localInput(end) };
}
export function Modal({ title, subtitle, children, onClose, wide = false }) {
  React.useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar"><Icon name="close" /></button></div>
      {children}
    </div>
  </div>;
}
export function Empty({ title, text, icon = 'calendar' }) {
  return <div className="empty"><span className="empty-icon"><Icon name={icon} size={26}/></span><strong>{title}</strong><p>{text}</p></div>;
}
