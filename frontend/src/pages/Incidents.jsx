import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle, Search, Filter, Clock, ChevronRight, Activity, ArrowUpDown, Loader } from 'lucide-react';
import { listIncidents } from '../api/servidor';
import './Incidents.css';

const severityColor = (sev) => {
  switch (sev) {
    case 'CRITICAL': return 'var(--status-critical)';
    case 'HIGH': return 'var(--tertiary)';
    case 'MEDIUM': return 'var(--status-warning)';
    default: return 'var(--on-surface-variant)';
  }
};

const statusDisplay = (status) => {
  switch (status) {
    case 'resolved': return { label: 'Resolved', dotClass: 'safe' };
    case 'analyzing': return { label: 'Analyzing', dotClass: 'active' };
    case 'plan_ready': return { label: 'Plan Ready', dotClass: 'warning' };
    case 'remediating': return { label: 'Remediating', dotClass: 'warning' };
    case 'detected': return { label: 'Detected', dotClass: 'critical' };
    default: return { label: status, dotClass: 'active' };
  }
};

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return isoStr;
  }
}

export default function Incidents() {
  const location = useLocation();
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('ALL');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.has('q')) {
      setSearchTerm(params.get('q'));
    }
  }, [location]);

  useEffect(() => {
    async function load() {
      try {
        const data = await listIncidents();
        setIncidents(data);
      } catch (e) {
        console.error('Failed to load incidents', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const mapped = incidents.map(inc => ({
    id: inc.incident_id,
    service: inc.anomaly?.service || '—',
    severity: (inc.anomaly?.severity || 'MEDIUM').toUpperCase(),
    status: inc.status,
    startedAt: inc.created_at,
    duration: inc.duration_seconds,
    summary: inc.anomaly?.problem || '—',
  }));

  const filtered = mapped.filter(inc => {
    const matchesSearch = inc.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.service.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.summary.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSeverity = filterSeverity === 'ALL' || inc.severity === filterSeverity;
    return matchesSearch && matchesSeverity;
  });

  const countBySeverity = (sev) => mapped.filter(i => i.severity === sev).length;

  if (loading) {
    return (
      <div className="incidents-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
        <Loader size={24} className="spin" color="var(--primary)" />
      </div>
    );
  }

  return (
    <div className="incidents-page">
      {/* Header */}
      <div className="incidents-header">
        <div className="incidents-title-row">
          <AlertTriangle size={22} color="var(--tertiary)" />
          <h2 className="text-page-title">Incident History</h2>
          <span className="incidents-count">{filtered.length} incidents</span>
        </div>
        <p className="incidents-subtitle">Review past incidents, their timelines, and remediation outcomes.</p>
      </div>

      {/* Toolbar */}
      <div className="incidents-toolbar">
        <div className="incidents-search">
          <Search size={16} className="search-icon" />
          <input
            id="incidents-search-input"
            type="text"
            className="input-field"
            placeholder="Search incidents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="incidents-filters">
          <Filter size={14} />
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => (
            <button
              key={sev}
              id={`filter-${sev.toLowerCase()}`}
              className={`filter-chip ${filterSeverity === sev ? 'filter-active' : ''}`}
              onClick={() => setFilterSeverity(sev)}
            >
              {sev === 'ALL' ? 'All' : sev.charAt(0) + sev.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Summary */}
      <div className="incidents-stats">
        <div className="stat-card">
          <span className="stat-value text-data-mono" style={{ color: 'var(--status-critical)' }}>{countBySeverity('CRITICAL')}</span>
          <span className="stat-label text-label-caps">Critical</span>
        </div>
        <div className="stat-card">
          <span className="stat-value text-data-mono" style={{ color: 'var(--tertiary)' }}>{countBySeverity('HIGH')}</span>
          <span className="stat-label text-label-caps">High</span>
        </div>
        <div className="stat-card">
          <span className="stat-value text-data-mono" style={{ color: 'var(--status-warning)' }}>{countBySeverity('MEDIUM')}</span>
          <span className="stat-label text-label-caps">Medium</span>
        </div>
        <div className="stat-card">
          <span className="stat-value text-data-mono" style={{ color: 'var(--status-safe)' }}>{countBySeverity('LOW')}</span>
          <span className="stat-label text-label-caps">Low</span>
        </div>
      </div>

      {/* Table */}
      <div className="incidents-table-wrapper card">
        <table className="incidents-table">
          <thead>
            <tr>
              <th><span className="th-content">ID <ArrowUpDown size={12} /></span></th>
              <th><span className="th-content">Service</span></th>
              <th><span className="th-content">Severity</span></th>
              <th><span className="th-content">Status</span></th>
              <th><span className="th-content">Started <ArrowUpDown size={12} /></span></th>
              <th><span className="th-content">Duration</span></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((inc) => {
              const st = statusDisplay(inc.status);
              return (
                <tr key={inc.id} className="incident-row">
                  <td className="text-data-mono incident-id">{inc.id}</td>
                  <td>
                    <div className="service-cell">
                      <Activity size={14} color="var(--primary)" />
                      <span>{inc.service}</span>
                    </div>
                  </td>
                  <td>
                    <span className="severity-badge" style={{ color: severityColor(inc.severity), borderColor: severityColor(inc.severity) }}>
                      {inc.severity}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${inc.status === 'resolved' ? 'resolved' : ''}`}>
                      <span className={`status-dot ${st.dotClass}`}></span>
                      {st.label}
                    </span>
                  </td>
                  <td className="text-body-base">
                    <span className="time-cell"><Clock size={13} />{formatTime(inc.startedAt)}</span>
                  </td>
                  <td className="text-data-mono">{formatDuration(inc.duration)}</td>
                  <td>
                    <button className="row-action" id={`view-${inc.id}`}>
                      <ChevronRight size={16} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="empty-table">
            <AlertTriangle size={40} color="var(--on-surface-variant)" strokeWidth={1} />
            <p>{mapped.length === 0 ? 'No incidents yet. Run a simulation from the Dashboard.' : 'No incidents match your filters.'}</p>
          </div>
        )}
      </div>
    </div>
  );
}
