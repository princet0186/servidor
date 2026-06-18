import { useState, useEffect } from 'react';
import { Shield, CheckCircle, XCircle, AlertTriangle, Clock, ChevronDown, ChevronUp, Lock, Unlock, Loader, Send } from 'lucide-react';
import { getSafetyValidations, validateAction } from '../api/servidor';
import './SafetyGate.css';

const riskColor = (risk) => {
  switch (risk) {
    case 'HIGH': case 'CRITICAL': return 'var(--status-critical)';
    case 'MEDIUM': return 'var(--status-warning)';
    default: return 'var(--status-safe)';
  }
};

function formatTimestamp(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleTimeString('en-US', { hour12: false }); }
  catch { return iso; }
}

export default function SafetyGate() {
  const [validations, setValidations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  // Live test state
  const [testAction, setTestAction] = useState('');
  const [testService, setTestService] = useState('vitals-ingestion-svc');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await getSafetyValidations();
        setValidations(data.validations || []);
      } catch (e) {
        console.error('Failed to load safety validations', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleTest = async () => {
    if (!testAction.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await validateAction(testAction, testService);
      setTestResult(result);
    } catch (e) {
      setTestResult({ error: e.message });
    } finally {
      setTesting(false);
    }
  };

  const approved = validations.filter(v => v.result === 'APPROVED').length;
  const blocked = validations.filter(v => v.result === 'BLOCKED').length;
  const totalChecks = validations.reduce((sum, v) => sum + (v.checks?.length || 0), 0);
  const passedChecks = validations.reduce((sum, v) => sum + (v.checks || []).filter(c => c.passed).length, 0);

  return (
    <div className="safety-page">
      {/* Header */}
      <div className="safety-header">
        <div className="safety-title-row">
          <Shield size={22} color="var(--secondary)" />
          <h2 className="text-page-title">Safety Gate</h2>
        </div>
        <p className="safety-subtitle">
          Every remediation action passes through safety validation before execution.
          Actions that risk patient harm are automatically blocked.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="safety-summary">
        <div className="safety-stat-card">
          <div className="safety-stat-icon" style={{ background: 'var(--status-safe-bg)' }}>
            <Unlock size={20} color="var(--status-safe)" />
          </div>
          <div className="safety-stat-info">
            <span className="stat-value text-data-mono" style={{ color: 'var(--status-safe)' }}>{approved}</span>
            <span className="stat-label text-label-caps">Approved</span>
          </div>
        </div>
        <div className="safety-stat-card">
          <div className="safety-stat-icon" style={{ background: 'var(--status-critical-bg)' }}>
            <Lock size={20} color="var(--status-critical)" />
          </div>
          <div className="safety-stat-info">
            <span className="stat-value text-data-mono" style={{ color: 'var(--status-critical)' }}>{blocked}</span>
            <span className="stat-label text-label-caps">Blocked</span>
          </div>
        </div>
        <div className="safety-stat-card">
          <div className="safety-stat-icon" style={{ background: 'var(--status-active-bg)' }}>
            <CheckCircle size={20} color="var(--status-active)" />
          </div>
          <div className="safety-stat-info">
            <span className="stat-value text-data-mono" style={{ color: 'var(--primary)' }}>{passedChecks}/{totalChecks}</span>
            <span className="stat-label text-label-caps">Checks passed</span>
          </div>
        </div>
      </div>

      {/* Live Test Section */}
      <div className="safety-test card">
        <h3 className="text-section-header">Test an Action</h3>
        <p className="safety-test-hint text-body-base">Try dangerous actions like "disable medication alerts" or "stop vitals ingestion" to see the safety gate in action.</p>
        <div className="safety-test-form">
          <input
            id="safety-test-action"
            type="text"
            className="input-field"
            placeholder='e.g. "disable medication alerts"'
            value={testAction}
            onChange={(e) => setTestAction(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleTest()}
          />
          <select
            id="safety-test-service"
            className="input-field safety-test-select"
            value={testService}
            onChange={(e) => setTestService(e.target.value)}
          >
            <option value="vitals-ingestion-svc">vitals-ingestion-svc</option>
            <option value="medication-alerts-svc">medication-alerts-svc</option>
            <option value="lab-routing-svc">lab-routing-svc</option>
          </select>
          <button className="btn btn-outline" id="safety-test-btn" onClick={handleTest} disabled={testing || !testAction.trim()}>
            {testing ? <Loader size={14} className="spin" /> : <Send size={14} />}
            Validate
          </button>
        </div>
        {testResult && (
          <div className={`safety-test-result ${testResult.allowed === false ? 'result-blocked' : testResult.error ? 'result-error' : 'result-allowed'}`}>
            {testResult.error ? (
              <span>⚠️ {testResult.error}</span>
            ) : testResult.allowed ? (
              <span><CheckCircle size={16} style={{ verticalAlign: 'middle' }} /> Action permitted: {testResult.action}</span>
            ) : (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                  <XCircle size={16} /> <strong>ACTION BLOCKED</strong>
                </div>
                <p style={{ margin: '4px 0', fontSize: '13px' }}>{testResult.refusal?.reason}</p>
                <p style={{ margin: '4px 0', fontSize: '12px', opacity: 0.8 }}>
                  Patients affected: {testResult.refusal?.patients_affected} • Required: {testResult.refusal?.required_approval}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Validation Cards */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <Loader size={24} className="spin" color="var(--primary)" />
        </div>
      ) : (
        <div className="safety-validations">
          {validations.length === 0 && (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--on-surface-variant)' }}>
              <Shield size={40} strokeWidth={1} style={{ marginBottom: '8px' }} />
              <p>No validations yet. Run a simulation from the Dashboard to see safety checks.</p>
            </div>
          )}
          {validations.map((val) => (
            <div key={val.id} className={`validation-card card ${val.result === 'BLOCKED' ? 'validation-blocked' : ''}`}>
              <div className="validation-header" onClick={() => setExpanded(expanded === val.id ? null : val.id)}>
                <div className="validation-result-icon">
                  {val.result === 'APPROVED'
                    ? <CheckCircle size={20} color="var(--status-safe)" />
                    : val.result === 'BLOCKED'
                      ? <XCircle size={20} color="var(--status-critical)" />
                      : <Clock size={20} color="var(--status-warning)" />
                  }
                </div>
                <div className="validation-info">
                  <span className="validation-action">{val.action}</span>
                  <span className="validation-meta text-body-base">
                    <span className="validation-target">{val.target}</span>
                    <span className="validation-sep">•</span>
                    <span className="validation-risk" style={{ color: riskColor(val.risk) }}>{val.risk} risk</span>
                    <span className="validation-sep">•</span>
                    <Clock size={12} /> {formatTimestamp(val.timestamp)}
                  </span>
                </div>
                <span className={`validation-result-badge ${val.result === 'APPROVED' ? 'badge-approved' : val.result === 'BLOCKED' ? 'badge-blocked' : 'badge-pending'}`}>
                  {val.result}
                </span>
                {expanded === val.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </div>

              {expanded === val.id && (
                <div className="validation-checks">
                  {(val.checks || []).map((check, i) => (
                    <div key={i} className="check-row">
                      <div className="check-icon">
                        {check.passed
                          ? <CheckCircle size={16} color="var(--status-safe)" />
                          : <XCircle size={16} color="var(--status-critical)" />
                        }
                      </div>
                      <div className="check-info">
                        <span className="check-name">{check.name}</span>
                        <span className="check-detail">{check.detail}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Bottom Info */}
      <div className="safety-footer card">
        <AlertTriangle size={16} color="var(--tertiary)" />
        <span className="text-body-base" style={{ color: 'var(--on-surface-variant)' }}>
          Safety Gate runs automatically during remediation. HIGH-risk blocked actions require manual supervisor override.
        </span>
      </div>
    </div>
  );
}
