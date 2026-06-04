import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function ScenarioCard({ title, patients, icu, workflows, isSimulating, onSimulate }) {
  return (
    <div className={`card ${isSimulating ? 'simulating' : ''}`} style={{
      borderColor: isSimulating ? 'var(--status-critical)' : 'var(--outline-variant)',
      transition: 'all 0.3s ease',
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--spacing-md)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 className="text-section-header">{title}</h3>
      </div>
      
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-sm)' }}>
          <span className="text-hero-metric" style={{ 
            color: isSimulating ? 'var(--status-critical)' : 'var(--on-surface)',
            fontSize: '32px'
          }}>
            {patients}
          </span>
          <span className="text-label-caps" style={{ color: 'var(--on-surface-variant)' }}>PATIENTS</span>
        </div>
        <div className="text-body-base" style={{ color: 'var(--on-surface-variant)', marginTop: 'var(--spacing-base)' }}>
          • {icu} ICU  • {workflows} Workflows
        </div>
      </div>
      
      <button 
        className="btn btn-danger-outline" 
        onClick={onSimulate}
        disabled={isSimulating}
        style={{ marginTop: 'auto', width: '100%', opacity: isSimulating ? 0.5 : 1 }}
      >
        <AlertTriangle size={16} />
        SIMULATE FAILURE
      </button>
    </div>
  );
}
