import React from 'react';
import { CheckCircle } from 'lucide-react';

export default function ComplianceReport({ report }) {
  if (!report) return null;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="text-section-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          <CheckCircle size={18} color="var(--status-safe)" />
          Compliance Report Generated
        </h2>
        <span className="text-label-caps" style={{ color: 'var(--status-safe)' }}>
          SECURE & PERSISTENT
        </span>
      </div>
      
      <div style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
        <div style={{ padding: 'var(--spacing-sm) var(--spacing-md)', background: 'var(--surface-container-lowest)', borderRadius: 'var(--radius-lg)' }}>
          <div className="text-data-mono">{report.patients_recovered} Patients Recovered</div>
        </div>
        <div style={{ padding: 'var(--spacing-sm) var(--spacing-md)', background: 'var(--surface-container-lowest)', borderRadius: 'var(--radius-lg)' }}>
          <div className="text-data-mono">{report.actions_taken} Actions Executed</div>
        </div>
        <div style={{ padding: 'var(--spacing-sm) var(--spacing-md)', background: 'var(--surface-container-lowest)', borderRadius: 'var(--radius-lg)' }}>
          <div className="text-data-mono">{report.unsafe_actions_blocked} Unsafe Actions Blocked</div>
        </div>
      </div>

      <div style={{ 
        padding: 'var(--spacing-md)', 
        background: 'var(--surface-container-lowest)', 
        borderRadius: 'var(--radius)',
        fontFamily: 'var(--font-inter)',
        fontSize: '14px',
        lineHeight: '1.6',
        color: 'var(--on-surface-variant)',
        whiteSpace: 'pre-wrap'
      }}>
        {report.narrative}
      </div>
      
      <div className="text-label-caps" style={{ color: 'var(--on-surface-variant)', textAlign: 'right' }}>
        Stored to MongoDB & Local JSON
      </div>
    </div>
  );
}
