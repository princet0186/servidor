import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, ArrowRight } from 'lucide-react';

export default function BlastRadius({ data, affectedService }) {
  const [count, setCount] = useState(0);
  const [expanded, setExpanded] = useState(false);
  
  const target = data?.patients_at_risk || 0;
  
  // Animate counter
  useEffect(() => {
    let startTime;
    const duration = 1200; // 1.2s
    
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

  // Helper for dependency graph pills
  const renderPill = (serviceName, isAffected) => (
    <span style={{ 
      background: isAffected ? 'var(--status-critical-bg)' : 'var(--surface-container-high)',
      color: isAffected ? 'var(--status-critical)' : 'var(--on-surface-variant)',
      border: `1px solid ${isAffected ? 'var(--status-critical)' : 'var(--outline-variant)'}`,
      padding: '2px 8px',
      borderRadius: 'var(--radius-sm)',
      fontFamily: 'var(--font-jetbrains)',
      fontSize: '12px'
    }}>
      {serviceName}
    </span>
  );

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      <div className="text-body-base" style={{ fontWeight: 600, color: 'var(--on-surface)' }}>
        Patients Affected
      </div>
      
      <div className="text-hero-metric" style={{ color: 'var(--status-critical)', fontSize: '56px', lineHeight: 1 }}>
        {count}
      </div>
      
      <div style={{ display: 'flex', gap: 'var(--spacing-lg)', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span className="text-body-base" style={{ fontWeight: 700, color: 'var(--primary)' }}>{data.critical_patients}</span>
          <span className="text-body-base" style={{ color: 'var(--on-surface-variant)' }}>ICU Critical</span>
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span className="text-body-base" style={{ fontWeight: 700, color: 'var(--on-surface)' }}>{data.affected_workflows?.length || 0}</span>
          <span className="text-body-base" style={{ color: 'var(--on-surface-variant)' }}>Workflows Disrupted</span>
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span className="text-body-base" style={{ fontWeight: 700, color: 'var(--primary)' }}>{data.estimated_harm_minutes} min</span>
          <span className="text-body-base" style={{ color: 'var(--on-surface-variant)' }}>to Harm</span>
        </div>
      </div>
      
      <div 
        style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', color: 'var(--primary)', marginTop: 'var(--spacing-sm)' }}
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="text-body-base">View affected wards</span>
      </div>
      
      {expanded && (
        <div style={{ 
          padding: 'var(--spacing-md)', 
          background: 'var(--surface-container-lowest)', 
          borderRadius: 'var(--radius)',
          fontFamily: 'var(--font-inter)',
          fontSize: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--spacing-sm)'
        }}>
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
      
      <hr style={{ borderTop: '1px solid var(--outline-variant)', borderBottom: 'none', margin: 'var(--spacing-md) 0' }} />
      
      <div className="text-body-base" style={{ color: 'var(--primary)', marginBottom: 'var(--spacing-sm)' }}>
        Service Dependencies
      </div>
      
      <div style={{ display: 'flex', gap: 'var(--spacing-lg)', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          {renderPill('vitals-ingestion', affectedService === 'vitals-ingestion' || affectedService === 'medication-alerts')}
          <ArrowRight size={16} color="var(--on-surface-variant)" />
          {renderPill('medication-alerts', affectedService === 'vitals-ingestion' || affectedService === 'medication-alerts')}
        </div>
        
        <div style={{ width: '1px', height: '16px', background: 'var(--outline-variant)' }}></div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          {renderPill('patient-portal', affectedService === 'lab-routing')}
          <ArrowRight size={16} color="var(--on-surface-variant)" />
          {renderPill('lab-routing', affectedService === 'lab-routing')}
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--status-critical)' }}></div>
          <span className="text-label-caps" style={{ color: 'var(--on-surface-variant)' }}>AFFECTED</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--outline)' }}></div>
          <span className="text-label-caps" style={{ color: 'var(--on-surface-variant)' }}>HEALTHY</span>
        </div>
      </div>
      
    </div>
  );
}
