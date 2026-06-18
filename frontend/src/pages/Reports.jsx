import { useState, useEffect } from 'react';
import { FileText, Download, Calendar, BarChart3, Clock, Filter, ChevronRight, TrendingDown, TrendingUp, Loader, Shield } from 'lucide-react';
import { getStats, listIncidents, listComplianceReports } from '../api/servidor';
import './Reports.css';

const typeColors = {
  SUMMARY: { bg: 'var(--status-active-bg)', color: 'var(--status-active)', border: 'rgba(32, 150, 243, 0.3)' },
  COMPLIANCE: { bg: 'var(--status-safe-bg)', color: 'var(--status-safe)', border: 'rgba(39, 174, 122, 0.3)' },
  SAFETY: { bg: 'rgba(203, 190, 255, 0.12)', color: 'var(--secondary)', border: 'rgba(203, 190, 255, 0.3)' },
};

function formatMTTR(seconds) {
  if (!seconds || seconds <= 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

export default function Reports() {
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [reports, setReports] = useState([]);

  useEffect(() => {
    async function load() {
      try {
        const [statsData, incidentsData, complianceData] = await Promise.all([
          getStats().catch(() => null),
          listIncidents().catch(() => []),
          listComplianceReports().catch(() => ({ reports: [] })),
        ]);
        setStats(statsData);

        // Build report cards from real data
        const builtReports = [];

        // Compliance reports from backend
        const compReports = complianceData.reports || [];
        compReports.forEach((r, i) => {
          builtReports.push({
            id: `RPT-C-${String(i + 1).padStart(3, '0')}`,
            title: `Compliance Report — ${r.incident_id}`,
            type: 'COMPLIANCE',
            period: r.incident_id,
            generated: r.generated_at ? new Date(r.generated_at).toLocaleDateString() : '—',
            incidents: 1,
            mttr: formatMTTR(r.duration_seconds),
            trend: 'down',
            patientsAtRisk: r.patients_at_risk || 0,
            narrative: r.narrative || '',
          });
        });

        // Build summary from incidents list
        const resolved = incidentsData.filter(i => i.status === 'resolved');
        if (resolved.length > 0) {
          const totalDuration = resolved.reduce((s, i) => s + (i.duration_seconds || 0), 0);
          const avgMttr = totalDuration / resolved.length;
          builtReports.push({
            id: 'RPT-S-001',
            title: 'Incident Summary',
            type: 'SUMMARY',
            period: 'All resolved incidents',
            generated: new Date().toLocaleDateString(),
            incidents: resolved.length,
            mttr: formatMTTR(avgMttr),
            trend: 'down',
          });
        }

        // Safety gate summary
        if (statsData && statsData.safety_gate) {
          builtReports.push({
            id: 'RPT-G-001',
            title: 'Safety Gate Effectiveness',
            type: 'SAFETY',
            period: 'All incidents',
            generated: new Date().toLocaleDateString(),
            incidents: statsData.total_incidents || 0,
            mttr: formatMTTR(statsData.avg_mttr_seconds),
            trend: 'down',
            safetyGate: statsData.safety_gate,
          });
        }

        setReports(builtReports);
      } catch (e) {
        console.error('Failed to load reports data', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = activeFilter === 'ALL'
    ? reports
    : reports.filter(r => r.type === activeFilter);

  if (loading) {
    return (
      <div className="reports-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
        <Loader size={24} className="spin" color="var(--primary)" />
      </div>
    );
  }

  return (
    <div className="reports-page">
      {/* Header */}
      <div className="reports-header">
        <div className="reports-title-row">
          <FileText size={22} color="var(--primary)" />
          <h2 className="text-page-title">Reports</h2>
        </div>
        <p className="reports-subtitle">
          Auto-generated incident summaries, compliance audits, and safety analytics.
        </p>
      </div>

      {/* KPI Row */}
      <div className="reports-kpis">
        <div className="kpi-card card">
          <div className="kpi-icon" style={{ background: 'var(--status-active-bg)' }}>
            <BarChart3 size={20} color="var(--status-active)" />
          </div>
          <div className="kpi-data">
            <span className="kpi-value text-data-mono">{stats?.total_incidents || 0}</span>
            <span className="kpi-label text-label-caps">Total Incidents</span>
          </div>
        </div>
        <div className="kpi-card card">
          <div className="kpi-icon" style={{ background: 'var(--status-safe-bg)' }}>
            <Clock size={20} color="var(--status-safe)" />
          </div>
          <div className="kpi-data">
            <span className="kpi-value text-data-mono">{formatMTTR(stats?.avg_mttr_seconds)}</span>
            <span className="kpi-label text-label-caps">Avg MTTR</span>
          </div>
        </div>
        <div className="kpi-card card">
          <div className="kpi-icon" style={{ background: 'rgba(203, 190, 255, 0.12)' }}>
            <Shield size={20} color="var(--secondary)" />
          </div>
          <div className="kpi-data">
            <span className="kpi-value text-data-mono">
              <span style={{ color: 'var(--status-safe)' }}>{stats?.safety_gate?.approved || 0}</span>
              <span style={{ color: 'var(--on-surface-variant)', fontSize: '14px' }}> / </span>
              <span style={{ color: 'var(--status-critical)' }}>{stats?.safety_gate?.blocked || 0}</span>
            </span>
            <span className="kpi-label text-label-caps">Approved / Blocked</span>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="reports-filter-bar">
        <Filter size={14} color="var(--on-surface-variant)" />
        {['ALL', 'SUMMARY', 'COMPLIANCE', 'SAFETY'].map(t => (
          <button
            key={t}
            id={`report-filter-${t.toLowerCase()}`}
            className={`filter-chip ${activeFilter === t ? 'filter-active' : ''}`}
            onClick={() => setActiveFilter(t)}
          >
            {t === 'ALL' ? 'All' : t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {/* Report Cards Grid */}
      <div className="reports-grid">
        {filtered.map((report) => {
          const style = typeColors[report.type] || typeColors.SUMMARY;
          return (
            <div key={report.id} className="report-card card">
              <div className="report-card-top">
                <span className="report-type-badge" style={{ background: style.bg, color: style.color, borderColor: style.border }}>
                  {report.type}
                </span>
                <span className="report-id text-data-mono">{report.id}</span>
              </div>
              <h3 className="report-title">{report.title}</h3>
              <div className="report-period">
                <Calendar size={13} />
                <span>{report.period}</span>
              </div>
              <div className="report-metrics">
                <div className="report-metric">
                  <span className="metric-val text-data-mono">{report.incidents}</span>
                  <span className="metric-label">incidents</span>
                </div>
                <div className="report-metric-sep"></div>
                <div className="report-metric">
                  <span className="metric-val text-data-mono">{report.mttr}</span>
                  <span className="metric-label">MTTR</span>
                </div>
                <div className="report-metric-sep"></div>
                <div className="report-metric">
                  {report.trend === 'down'
                    ? <TrendingDown size={16} color="var(--status-safe)" />
                    : <TrendingUp size={16} color="var(--status-critical)" />
                  }
                  <span className="metric-label">{report.trend === 'down' ? 'Improving' : 'Worsening'}</span>
                </div>
              </div>
              <div className="report-card-actions">
                <button className="btn btn-outline" id={`view-${report.id}`}>
                  <ChevronRight size={14} /> View
                </button>
                <button className="btn btn-outline" id={`download-${report.id}`}>
                  <Download size={14} /> Export
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="reports-empty card">
          <FileText size={40} color="var(--on-surface-variant)" strokeWidth={1} />
          <p>{reports.length === 0 ? 'No reports yet. Complete a simulation to generate compliance reports.' : 'No reports match the selected filter.'}</p>
        </div>
      )}
    </div>
  );
}
