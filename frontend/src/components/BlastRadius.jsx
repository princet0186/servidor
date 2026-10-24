import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, ArrowRight } from 'lucide-react';

export default function BlastRadius({ data, affectedService }) {
  const [count, setCount] = useState(0);
  const [expanded, setExpanded] = useState(false);
  
  const target = data?.patients_at_risk || 0;
  
  // Animate counter
  useEffect(() => {
    let startTime;
    const duration = 1200;
    
    const animate = (time) => {
      if (!startTime) startTime = time;
      const progress = (time - startTime) / duration;
      
      if (progress < 1) {
        const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        setCount(Math.floor(easeProgress * target));
        requestAnimationFrame(animate);
      } else {
        setCount(target);
      }
    };
    
    if (target > 0) {
      requestAnimationFrame(animate);
    }
  }, [target]);

  if (!data) return null;

  const isAffected = (svc) => {
    if (!affectedService) return false;
    if (svc === affectedService) return true;
    if (affectedService === 'vitals-ingestion' && svc === 'medication-alerts') return true;
    if (affectedService === 'medication-alerts' && svc === 'vitals-ingestion') return true;
    if (affectedService === 'lab-routing' && svc === 'patient-portal') return true;
    return false;
  };

  return (
    <div className="card blast-radius-card">
      <div className="text-body-base" style={{ fontWeight: 600 }}>
        Patients Affected
      </div>
      
      <div className="blast-hero-row">
        <span className="text-hero-metric" style={{ color: 'var(--status-critical)', fontSize: '56px', lineHeight: 1 }}>
          {count}
        </span>
      </div>
      
      <div className="blast-stat-row">
        <div className="blast-stat">
          <span className="text-body-base blast-stat-value" style={{ color: 'var(--primary)' }}>{data.critical_patients}</span>
          <span className="text-body-base" style={{ color: 'var(--on-surface-variant)' }}>ICU Critical</span>
        </div>
        <div className="blast-stat">
          <span className="text-body-base blast-stat-value">{data.affected_workflows?.length || 0}</span>
          <span className="text-body-base" style={{ color: 'var(--on-surface-variant)' }}>Workflows Disrupted</span>
        </div>
        <div className="blast-stat">
          <span className="text-body-base blast-stat-value" style={{ color: 'var(--primary)' }}>{data.estimated_harm_minutes} min</span>
          <span className="text-body-base" style={{ color: 'var(--on-surface-variant)' }}>to Harm</span>
        </div>
      </div>
      
      <button className="blast-wards-toggle" onClick={() => setExpanded(!expanded)}>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>View affected wards</span>
      </button>
      
      {expanded && (
        <div className="blast-wards-panel">
          {data.affected_wards?.map((ward, i) => (
            <div key={i}>
              <strong>{ward.ward_name}, Floor {ward.floor}</strong> — Beds {ward.beds.map(b => b.bed).join(', ')}
            </div>
          ))}
          {data.general_wards?.map((ward, i) => (
            <div key={i} style={{ color: 'var(--on-surface-variant)' }}>
              {ward.ward_name}, Floor {ward.floor} — {ward.beds_affected} beds affected
            </div>
          ))}
          {(!data.affected_wards?.length && !data.general_wards?.length) && (
            <div style={{ color: 'var(--on-surface-variant)', fontStyle: 'italic' }}>No specific ward data available.</div>
          )}
        </div>
      )}
      
      <hr className="blast-divider" />
      
      <div className="text-body-base blast-deps-label">Service Dependencies</div>
      
      <div className="blast-deps-row">
        <div className="blast-dep-chain">
          <span className={`blast-dep-pill ${isAffected('vitals-ingestion') ? 'affected' : 'healthy'}`}>vitals-ingestion</span>
          <ArrowRight size={16} color="var(--on-surface-variant)" />
          <span className={`blast-dep-pill ${isAffected('medication-alerts') ? 'affected' : 'healthy'}`}>medication-alerts</span>
        </div>
        
        <div style={{ width: '1px', height: '16px', background: 'var(--outline-variant)' }}></div>
        
        <div className="blast-dep-chain">
          <span className={`blast-dep-pill ${isAffected('patient-portal') ? 'affected' : 'healthy'}`}>patient-portal</span>
          <ArrowRight size={16} color="var(--on-surface-variant)" />
          <span className={`blast-dep-pill ${isAffected('lab-routing') ? 'affected' : 'healthy'}`}>lab-routing</span>
        </div>
      </div>
      
      <div className="blast-legend">
        <div className="blast-legend-item">
          <div className="blast-legend-dot" style={{ background: 'var(--status-critical)' }}></div>
          <span className="text-label-caps" style={{ color: 'var(--on-surface-variant)' }}>AFFECTED</span>
        </div>
        <div className="blast-legend-item">
          <div className="blast-legend-dot" style={{ background: 'var(--outline)' }}></div>
          <span className="text-label-caps" style={{ color: 'var(--on-surface-variant)' }}>HEALTHY</span>
        </div>
      </div>
    </div>
  );
}
