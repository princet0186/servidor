import React, { useState } from 'react';
import { CheckCircle, Hourglass, ChevronRight, ChevronDown } from 'lucide-react';

export default function ReasoningTimeline({ logs, active, remediationPlan, onStepApproved, onStepRejected }) {
  const [expandedIndex, setExpandedIndex] = useState(logs?.length - 1 || 0);
  
  const pendingSteps = remediationPlan?.filter(s => s.status === 'pending') || [];
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', marginTop: 'var(--spacing-md)' }}>
      <h2 className="text-label-caps" style={{ color: 'var(--on-surface)', marginBottom: 'var(--spacing-lg)' }}>
        AGENT REASONING TIMELINE
      </h2>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
        {(!logs || logs.length === 0) && (
          <div className="text-body-base" style={{ color: 'var(--on-surface-variant)', fontStyle: 'italic' }}>
            Waiting for events...
          </div>
        )}
        
        {logs?.map((log, i) => {
          const isLast = i === logs.length - 1 && pendingSteps.length === 0;
          const isExpanded = expandedIndex === i;
          
          let dotClass = 'safe';
          let Icon = CheckCircle;
          let iconColor = 'var(--status-safe)';
          
          if (log.event_type === 'refusal') {
            dotClass = 'critical';
            iconColor = 'var(--status-critical)';
          }
          if (log.event_type === 'rejection') {
            dotClass = 'warning';
            iconColor = 'var(--status-warning)';
          }
          
          return (
            <div key={i} style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '12px' }}>
                <div className={`status-dot ${dotClass}`} style={{ marginTop: '8px' }}></div>
                {!isLast && <div style={{ width: '1px', flex: 1, backgroundColor: 'var(--outline-variant)', marginTop: '8px', marginBottom: '8px' }}></div>}
              </div>
              
              <div style={{ flex: 1, paddingBottom: isLast ? '0' : 'var(--spacing-lg)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
                    <span className="text-data-mono" style={{ color: 'var(--on-surface-variant)' }}>{log.timestamp}</span>
                    <span className="text-body-base" style={{ fontWeight: 600, color: 'var(--primary)' }}>{log.title}</span>
                  </div>
                  <Icon size={20} color={iconColor} />
                </div>
                
                <div className="text-body-base" style={{ color: 'var(--on-surface-variant)', marginTop: '4px' }}>
                  {log.content.split('\n')[0]} {/* Show first line as snippet */}
                </div>
                
                {log.content.includes('\n') && (
                  <div 
                    style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginTop: '8px', cursor: 'pointer', color: 'var(--primary)' }}
                    onClick={() => setExpandedIndex(isExpanded ? -1 : i)}
                  >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span className="text-body-base">Expand reasoning</span>
                  </div>
                )}
                
                {isExpanded && log.content.includes('\n') && (
                  <div 
                    className="text-data-mono" 
                    style={{ 
                      marginTop: 'var(--spacing-sm)', 
                      color: 'var(--on-surface-variant)',
                      whiteSpace: 'pre-wrap'
                    }}
                  >
                    {log.content.substring(log.content.indexOf('\n') + 1)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        
        {/* Render pending approvals at the end of the timeline */}
        {pendingSteps.map((step, i) => (
          <div key={`pending-${i}`} style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '12px' }}>
              <div className="status-dot warning" style={{ marginTop: '8px' }}></div>
            </div>
            
            <div style={{ flex: 1, paddingBottom: '0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
                  <span className="text-data-mono" style={{ color: 'var(--on-surface-variant)' }}>
                    {new Date().toLocaleTimeString('en-US', { hour12: false })}
                  </span>
                  <span className="text-body-base" style={{ fontWeight: 600, color: 'var(--primary)' }}>Waiting for approval...</span>
                </div>
                <Hourglass size={20} color="var(--status-warning)" />
              </div>
              
              <div className="text-body-base" style={{ color: 'var(--on-surface-variant)', marginTop: '4px' }}>
                Step {step.order}: {step.action} ({step.risk_level.toLowerCase()} risk)
              </div>
              
              <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginTop: '12px' }}>
                <button 
                  className="btn" 
                  style={{ 
                    background: 'transparent', 
                    color: 'var(--status-safe)',
                    border: '1px solid var(--status-safe)',
                    padding: '6px 16px',
                    fontSize: '12px',
                    fontWeight: 600,
                    letterSpacing: '0.05em'
                  }}
                  onClick={() => onStepApproved(step.order)}
                >
                  APPROVE
                </button>
                <button 
                  className="btn" 
                  style={{ 
                    background: 'transparent',
                    color: 'var(--on-surface-variant)',
                    border: '1px solid var(--outline-variant)',
                    padding: '6px 16px',
                    fontSize: '12px',
                    fontWeight: 600,
                    letterSpacing: '0.05em'
                  }}
                  onClick={() => onStepRejected(step.order)}
                >
                  REJECT
                </button>
              </div>
            </div>
          </div>
        ))}
        
      </div>
    </div>
  );
}
