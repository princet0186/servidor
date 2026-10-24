import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Clock, Shield, FileText, Users, Activity, CheckCircle, XCircle, Loader } from 'lucide-react';
import { getIncident, approveStep, rejectStep, resetIncident, getBriefings, getComplianceReport, getFacility, getDependencyGraph, getServices } from '../api/servidor';
import ClinicalTwinPanel from '../components/twin/ClinicalTwinPanel';
import BlastRadius from '../components/BlastRadius';
import IncidentBriefing from '../components/IncidentBriefing';
import ComplianceReport from '../components/ComplianceReport';
import './IncidentDetail.css';
import { parseServerTime } from '../utils/time';

const riskColor = (risk) => {
  switch (risk) {
    case 'HIGH': case 'CRITICAL': return { color: 'var(--status-critical)', bg: 'var(--status-critical-bg)' };
    case 'MEDIUM': return { color: 'var(--status-warning)', bg: 'var(--status-warning-bg)' };
    default: return { color: 'var(--status-safe)', bg: 'var(--status-safe-bg)' };
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
    return parseServerTime(isoStr).toLocaleString('en-US', { 
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false 
    });
  } catch {
    return isoStr;
  }
}

// Incident plus its briefings and compliance report (each optional).
async function fetchIncidentBundle(incidentId) {
  const bundle = { incident: null, briefings: null, compliance: null };
  try {
    const inc = await getIncident(incidentId);
    bundle.incident = inc;
    bundle.briefings = inc.briefings || await getBriefings(incidentId).catch(() => null);
    bundle.compliance = inc.compliance_report || await getComplianceReport(incidentId).catch(() => null);
  } catch (e) {
    console.error('Failed to load incident', e);
  }
  return bundle;
}

export default function IncidentDetail() {
  const { incidentId } = useParams();
  const navigate = useNavigate();
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [briefings, setBriefings] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [twinData, setTwinData] = useState(null);

  useEffect(() => {
    let active = true;
    Promise.all([getFacility(), getDependencyGraph(), getServices()])
      .then(([facility, graph, services]) => { if (active) setTwinData({ facility, graph, services }); })
      .catch((e) => console.error('Failed to load twin data', e));
    return () => { active = false; };
  }, []);

  function apply(bundle) {
    if (bundle.incident) setIncident(bundle.incident);
    if (bundle.briefings) setBriefings(bundle.briefings);
    if (bundle.compliance) setCompliance(bundle.compliance);
    setLoading(false);
  }

  async function loadIncident() {
    apply(await fetchIncidentBundle(incidentId));
  }

  useEffect(() => {
    let active = true;
    fetchIncidentBundle(incidentId).then((bundle) => { if (active) apply(bundle); });
    return () => { active = false; };
  }, [incidentId]);

  if (loading) {
    return (
      <div className="incident-detail" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader size={24} className="spin" color="var(--primary)" />
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="incident-detail" style={{ textAlign: 'center', padding: '60px' }}>
        <AlertTriangle size={40} color="var(--on-surface-variant)" strokeWidth={1} />
        <p style={{ marginTop: '12px', color: 'var(--on-surface-variant)' }}>Incident not found.</p>
        <button className="btn btn-outline" onClick={() => navigate('/incidents')} style={{ marginTop: '16px' }}>
          <ArrowLeft size={14} /> Back to Incidents
        </button>
      </div>
    );
  }

  const anomaly = incident.anomaly || {};
  const severity = (anomaly.severity || 'MEDIUM').toUpperCase();
  const service = anomaly.service || '—';
  const problem = anomaly.problem || '—';
  const br = incident.blast_radius;
  const plan = incident.remediation_plan || [];
  const audit = incident.audit_trail || [];

  const affectedService = service.includes('vitals') ? 'vitals-ingestion' 
    : service.includes('medication') ? 'medication-alerts' 
    : service.includes('lab') ? 'lab-routing' : null;

  return (
    <div className="incident-detail anim-fade-in">
      {/* Header */}
      <div className="incident-detail-header">
        <div>
          <div className="incident-detail-title-row">
            <button className="btn btn-outline" onClick={() => navigate('/incidents')} style={{ padding: '4px 8px', height: '28px' }}>
              <ArrowLeft size={14} />
            </button>
            <span className="incident-detail-id">{incident.incident_id}</span>
            <span className={`incident-status-badge ${incident.status}`}>
              <span className={`status-dot ${incident.status === 'resolved' ? 'safe' : incident.status === 'detected' ? 'critical' : 'warning'}`}></span>
              {incident.status.replace('_', ' ')}
            </span>
          </div>
          <div className="incident-detail-meta">
            <span><Clock size={13} /> {formatTime(incident.created_at)}</span>
            <span>•</span>
            <span><Activity size={13} /> {service}</span>
            <span>•</span>
            <span style={{ color: riskColor(severity).color }}>{severity} severity</span>
          </div>
          <p className="text-body-base" style={{ marginTop: 'var(--spacing-sm)', color: 'var(--on-surface-variant)' }}>
            {problem}
          </p>
        </div>
        <div className="incident-detail-actions">
          <button className="btn btn-outline" onClick={() => { resetIncident(incidentId); navigate('/incidents'); }}>
            Reset
          </button>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="incident-summary-grid">
        <div className="card incident-summary-card anim-slide-up anim-delay-1">
          <span className="summary-label">Patients at Risk</span>
          <span className="summary-value" style={{ color: 'var(--status-critical)' }}>{br?.patients_at_risk || 0}</span>
          <span className="summary-sub">{br?.critical_patients || 0} in ICU</span>
        </div>
        <div className="card incident-summary-card anim-slide-up anim-delay-2">
          <span className="summary-label">Time to Harm</span>
          <span className="summary-value" style={{ color: 'var(--status-warning)' }}>{br?.estimated_harm_minutes || '—'}</span>
          <span className="summary-sub">minutes</span>
        </div>
        <div className="card incident-summary-card anim-slide-up anim-delay-3">
          <span className="summary-label">Duration</span>
          <span className="summary-value" style={{ color: 'var(--primary)' }}>{formatDuration(incident.duration_seconds)}</span>
          <span className="summary-sub">total response time</span>
        </div>
        <div className="card incident-summary-card anim-slide-up anim-delay-4">
          <span className="summary-label">Recovery Steps</span>
          <span className="summary-value">{plan.filter(s => s.status === 'completed').length}/{plan.length}</span>
          <span className="summary-sub">completed</span>
        </div>
      </div>

      {/* 3D replay of the clinical blast radius */}
      {br && (
        <div className="anim-scale-in anim-delay-1">
          <ClinicalTwinPanel
            facility={twinData?.facility}
            graph={twinData?.graph}
            servicesMap={twinData?.services}
            health={[]}
            blast={br}
            failingService={affectedService ? `${affectedService}-svc` : null}
            incidentId={incident.incident_id}
            replay
            fallback={null}
          />
        </div>
      )}

      {/* Blast Radius + Briefings */}
      {br && (
        <div className="incident-detail-grid anim-scale-in anim-delay-2">
          <BlastRadius data={br} affectedService={affectedService} />
          {briefings && <IncidentBriefing briefings={briefings} />}
        </div>
      )}

      {/* Remediation Plan */}
      {plan.length > 0 && (
        <div className="card remediation-section anim-slide-up anim-delay-3" style={{ padding: 'var(--spacing-md)' }}>
          <h3 className="text-section-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
            <Shield size={18} color="var(--secondary)" />
            Recovery Plan
          </h3>
          {plan.map((step) => {
            const rc = riskColor(step.risk_level);
            const statusClass = step.status === 'completed' || step.status === 'approved' ? 'completed' : step.status === 'rejected' ? 'rejected' : 'pending';
            return (
              <div key={step.step_id || step.order} className="remediation-step">
                <div className={`remediation-step-number ${statusClass}`}>
                  {step.status === 'completed' ? <CheckCircle size={16} /> : step.status === 'rejected' ? <XCircle size={16} /> : step.order}
                </div>
                <div className="remediation-step-body">
                  <span className="remediation-step-title">{step.description}</span>
                  <div className="remediation-step-meta">
                    <span className="risk-tag" style={{ color: rc.color, background: rc.bg }}>{step.risk_level}</span>
                    <span>Confidence: {Math.round((step.confidence || 0) * 100)}%</span>
                    <span>Status: {step.status}</span>
                    {step.executed_at && <span>Executed: {formatTime(step.executed_at)}</span>}
                  </div>
                </div>
                {step.status === 'pending' && (
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button className="btn-approve" onClick={async () => { await approveStep(incidentId, step.order); loadIncident(); }}>APPROVE</button>
                    <button className="btn-reject" onClick={async () => { await rejectStep(incidentId, step.order); loadIncident(); }}>REJECT</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Compliance Report */}
      {compliance && (
        <div className="anim-slide-up anim-delay-4">
          <ComplianceReport report={compliance} />
        </div>
      )}

      {/* Audit Trail */}
      {audit.length > 0 && (
        <div className="card anim-slide-up anim-delay-5" style={{ padding: 'var(--spacing-md)' }}>
          <h3 className="text-section-header" style={{ marginBottom: 'var(--spacing-md)', display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
            <FileText size={18} color="var(--primary)" />
            Full Audit Trail
          </h3>
          <div className="audit-section">
            {audit.map((entry, i) => (
              <div key={i} className="audit-entry">
                <span className="audit-entry-time">
                  {entry.timestamp ? parseServerTime(entry.timestamp).toLocaleTimeString('en-US', { hour12: false }) : '—'}
                </span>
                <span className="audit-entry-type" style={{ 
                  color: entry.event_type === 'refusal' ? 'var(--status-critical)' : 
                         entry.event_type === 'resolution' ? 'var(--status-safe)' : 'var(--primary)' 
                }}>
                  {entry.event_type}
                </span>
                <span className="audit-entry-message">{entry.message}</span>
                {entry.confidence && (
                  <span className="text-data-mono" style={{ color: 'var(--on-surface-variant)', fontSize: '11px' }}>
                    {Math.round(entry.confidence * 100)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
