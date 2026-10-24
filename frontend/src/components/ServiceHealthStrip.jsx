import React from 'react';
import { Radio } from 'lucide-react';

const LABELS = {
  'vitals-ingestion-svc': 'Vitals Ingestion',
  'medication-alerts-svc': 'Medication Alerts',
  'lab-routing-svc': 'Lab Routing',
  'patient-portal-svc': 'Patient Portal',
};

function dotClass(status) {
  if (status === 'healthy') return 'safe';
  if (status === 'down') return 'pulse-critical';
  return 'critical';
}

// Live measurements from the agent's own probes against the running services.
export default function ServiceHealthStrip({ health, platform }) {
  if (!health || health.length === 0) return null;

  return (
    <div className="card health-strip">
      <div className="health-strip-header">
        <span className="text-label-caps"><Radio size={12} /> Live probes</span>
        <span className="text-label-caps health-strip-platform">
          {platform === 'cloud_run' ? 'GOOGLE CLOUD RUN' : 'LOCAL'}
        </span>
      </div>
      <div className="health-strip-grid">
        {health.map((svc) => (
          <div key={svc.service} className={`health-cell ${svc.status !== 'healthy' ? 'unhealthy' : ''}`}>
            <div className="health-cell-name">
              <div className={`status-dot ${dotClass(svc.status)}`}></div>
              <span>{LABELS[svc.service] || svc.service}</span>
            </div>
            <div className="health-cell-metrics text-data-mono">
              <span>{Math.round(svc.median_latency_ms)} ms</span>
              <span>{Math.round(svc.error_rate * 100)}% err</span>
            </div>
            <div className="health-cell-revision text-data-mono">
              {svc.revision || '—'}{svc.release ? ` · ${svc.release}` : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
