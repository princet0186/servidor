import React from 'react';

export default function DependencyGraph({ affectedService }) {
  // SVG viewBox size
  const width = 600;
  const height = 250;
  
  const nodes = [
    { id: 'vitals-ingestion', label: 'Vitals Monitoring', x: 150, y: 150 },
    { id: 'medication-alerts', label: 'Medication Safety', x: 300, y: 70 },
    { id: 'lab-routing', label: 'Lab Results', x: 300, y: 220 },
    { id: 'patient-portal', label: 'Patient Portal', x: 450, y: 150 },
  ];
  
  const edges = [
    { source: 'vitals-ingestion', target: 'medication-alerts' },
    { source: 'vitals-ingestion', target: 'patient-portal' },
    { source: 'lab-routing', target: 'patient-portal' },
  ];
  
  const isAffected = (id) => {
    if (!affectedService) return false;
    // Highlight the root cause and downstream
    if (id === affectedService) return true;
    if (affectedService === 'vitals-ingestion' && id !== 'lab-routing') return true;
    if (affectedService === 'lab-routing' && id === 'patient-portal') return true;
    return false;
  };

  return (
    <div style={{ 
      width: '100%', 
      display: 'flex', 
      justifyContent: 'center', 
      background: 'var(--surface-container-lowest)', 
      borderRadius: 'var(--radius-xl)',
      padding: 'var(--spacing-md)'
    }}>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="var(--outline-variant)" />
          </marker>
          <marker id="arrowhead-critical" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="var(--status-critical)" />
          </marker>
        </defs>
        
        {/* Draw edges */}
        {edges.map((edge, i) => {
          const src = nodes.find(n => n.id === edge.source);
          const tgt = nodes.find(n => n.id === edge.target);
          
          const affected = isAffected(src.id) && isAffected(tgt.id);
          const stroke = affected ? 'var(--status-critical)' : 'var(--outline-variant)';
          const marker = affected ? 'url(#arrowhead-critical)' : 'url(#arrowhead)';
          const dash = affected ? '5,5' : 'none';
          
          return (
            <line 
              key={i}
              x1={src.x} y1={src.y} 
              x2={tgt.x} y2={tgt.y}
              stroke={stroke}
              strokeWidth="1.5"
              strokeDasharray={dash}
              markerEnd={marker}
              style={{ transition: 'stroke 0.6s ease' }}
            />
          );
        })}
        
        {/* Draw nodes */}
        {nodes.map(node => {
          const affected = isAffected(node.id);
          const bg = affected ? 'var(--status-critical-bg)' : 'var(--surface-container)';
          const border = affected ? 'var(--status-critical)' : 'var(--outline)';
          const textColor = affected ? 'var(--status-critical)' : 'var(--on-surface)';
          
          return (
            <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
              <rect 
                x="-65" y="-20" 
                width="130" height="40" 
                rx="6" ry="6"
                fill={bg}
                stroke={border}
                strokeWidth="1"
                style={{ transition: 'all 0.6s ease' }}
              />
              <text 
                textAnchor="middle" 
                dominantBaseline="middle"
                fill={textColor}
                className="text-label-caps"
                style={{ transition: 'fill 0.6s ease' }}
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
