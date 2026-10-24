import React from 'react';
import { CheckCircle } from 'lucide-react';

export default function ComplianceReport({ report }) {
  if (!report) return null;

  return (
    <div className="card compliance-card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      <div className="compliance-header">
        <h2 className="text-section-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          <CheckCircle size={18} color="var(--status-safe)" />
          Compliance Report Generated
        </h2>
        <span className="text-label-caps" style={{ color: 'var(--status-safe)' }}>
          SECURE & PERSISTENT
        </span>
      </div>
      
      <div className="compliance-stats">
        <div className="compliance-stat-chip">
          <div className="text-data-mono">{report.patients_recovered} Patients Recovered</div>
        </div>
        <div className="compliance-stat-chip">
          <div className="text-data-mono">{report.actions_taken} Actions Executed</div>
        </div>
        <div className="compliance-stat-chip">
          <div className="text-data-mono">{report.unsafe_actions_blocked} Unsafe Actions Blocked</div>
        </div>
      </div>

      <div className="compliance-narrative">
        {report.narrative}
      </div>
      
      <div className="text-label-caps compliance-footer">
        Stored to MongoDB & Local JSON
      </div>
    </div>
  );
}
