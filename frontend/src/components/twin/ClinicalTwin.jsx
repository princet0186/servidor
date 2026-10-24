import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Layers, RotateCcw, Maximize2, Minimize2, Pause, Play, Hand } from 'lucide-react';
import TwinScene from './TwinScene';
import { EXPLODED_VIEW, HOME_VIEW, SERVICE_LABELS, buildLayout, computeImpact, floorY, serviceFeeds, servicePositions } from './layout';
import './ClinicalTwin.css';

function TooltipBody({ hovered }) {
  if (hovered.kind === 'bed') {
    const info = hovered.bed.info;
    return (
      <>
        <strong>{hovered.ward.name} · Bed {hovered.bed.id}</strong>
        {info ? (
          <>
            <span>{info.protocol} · acuity {info.acuity}</span>
            <span className="twin-tip-critical">NEWS2 {info.news2_score} · real-time monitoring lost</span>
          </>
        ) : hovered.level === 'warning' ? (
          <span className="twin-tip-warning">Affected workflow · manual checks advised</span>
        ) : (
          <span>Monitoring nominal</span>
        )}
      </>
    );
  }
  if (hovered.kind === 'ward') {
    return (
      <>
        <strong>{hovered.ward.name}</strong>
        <span>Floor {hovered.ward.floor} · {hovered.ward.beds.length} beds · {hovered.ward.specialty?.replaceAll('_', ' ')}</span>
        <span>Click to fly in</span>
      </>
    );
  }
  const p = hovered.probe;
  return (
    <>
      <strong>{SERVICE_LABELS[hovered.id] || hovered.id}</strong>
      {p ? <span>median {Math.round(p.median_latency_ms)} ms · {Math.round(p.error_rate * 100)}% errors (live probe)</span> : <span>no probe data</span>}
      {p?.revision && <span>revision {p.revision}{p.release ? ` · ${p.release}` : ''}</span>}
    </>
  );
}

// Clinical digital twin: live services below, the hospital above, and the blast between them.
export default function ClinicalTwin({ facility, graph, servicesMap, health, blast, failingService, incidentId, resolved, replay }) {
  const wrapper = useRef();
  const [explode, setExplode] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [hovered, setHovered] = useState(null);
  const pausedRef = useRef(false);
  const onHover = useCallback((h) => {
    pausedRef.current = Boolean(h);
    setHovered(h);
  }, []);
  const [focus, setFocus] = useState(null);
  const [touched, setTouched] = useState(false);

  const layout = useMemo(() => buildLayout(facility), [facility]);
  const serviceIds = useMemo(() => (graph?.nodes || []).map((n) => n.id), [graph]);
  const servicePos = useMemo(() => servicePositions(serviceIds), [serviceIds]);
  const feeds = useMemo(() => serviceFeeds(servicesMap), [servicesMap]);
  const liveBlast = resolved ? null : blast;
  const liveFailing = resolved ? null : failingService;
  const impact = useMemo(
    () => computeImpact({ blast: liveBlast, failingService: liveFailing, graph, health }),
    [liveBlast, liveFailing, graph, health]
  );
  const revealKey = liveBlast ? incidentId || 'incident' : null;

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === wrapper.current);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else wrapper.current?.requestFullscreen?.();
  };

  const focusWard = useCallback((ward) => {
    const y = floorY(ward.floor, explode ? 1 : 0);
    setAutoRotate(false);
    setFocus({ target: [ward.x, y, ward.z], position: [ward.x + 2.6, y + 2.8, ward.z + 4.4], key: Date.now() });
  }, [explode]);

  const resetView = () => setFocus({ ...(explode ? EXPLODED_VIEW : HOME_VIEW), key: Date.now() });

  const toggleExplode = () => {
    const next = !explode;
    setExplode(next);
    // Pull the camera back to fit the separated floors, like a product teardown view
    setFocus({ ...(next ? EXPLODED_VIEW : HOME_VIEW), key: Date.now() });
  };

  const state = resolved ? 'recovered' : liveBlast ? 'incident' : impact.unhealthy.size ? 'detecting' : 'live';
  const stateLabel = replay
    ? `INCIDENT REPLAY · ${incidentId}`
    : { live: 'ALL SYSTEMS NOMINAL', detecting: 'ANOMALY DETECTED', incident: 'CLINICAL BLAST RADIUS', recovered: 'RECOVERED' }[state];
  const totalBeds = layout.wards.reduce((s, w) => s + w.beds.length, 0);
  const icuAtRisk = Object.keys(impact.icuBeds).length;

  return (
    <div ref={wrapper} className={`twin ${fullscreen ? 'twin-fullscreen' : ''} twin-state-${state}`}>
      <Canvas
        camera={{ position: HOME_VIEW.position, fov: 40, near: 0.1, far: 120 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: 'high-performance' }}
        onPointerDown={() => setTouched(true)}
        onPointerMissed={() => onHover(null)}
        onWheel={() => setTouched(true)}
      >
        <TwinScene
          layout={layout}
          impact={impact}
          feeds={feeds}
          servicePos={servicePos}
          failingService={liveFailing}
          health={health}
          explode={explode}
          revealKey={revealKey}
          autoRotate={autoRotate}
          pausedRef={pausedRef}
          focus={focus}
          onHover={onHover}
          onWardClick={focusWard}
        />
      </Canvas>

      {hovered?.screen && (
        <div className="twin-tooltip" style={{ left: hovered.screen[0], top: hovered.screen[1] }}>
          <TooltipBody hovered={hovered} />
        </div>
      )}

      <div className="twin-hud twin-hud-top">
        <div className="twin-title">
          <span className="twin-eyebrow">Clinical digital twin</span>
          <span className={`twin-state twin-state-chip-${state}`}><i />{stateLabel}</span>
          <span className="twin-sub">
            {layout.floors.length} floors · {totalBeds} beds · {serviceIds.length} live services
          </span>
        </div>
        <div className="twin-controls">
          <button className={explode ? 'on' : ''} onClick={toggleExplode} title="Explode floors">
            <Layers size={15} /><span>{explode ? 'Stack floors' : 'Explode floors'}</span>
          </button>
          <button onClick={resetView} title="Reset view"><RotateCcw size={15} /></button>
          <button className={autoRotate ? 'on' : ''} onClick={() => setAutoRotate((v) => !v)} title={autoRotate ? 'Pause rotation' : 'Auto-rotate'}>
            {autoRotate ? <Pause size={15} /> : <Play size={15} />}
          </button>
          <button onClick={toggleFullscreen} title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}>
            {fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </div>
      </div>

      {liveBlast && (
        <div className="twin-hud twin-stats">
          <div><b className="crit">{liveBlast.patients_at_risk}</b><span>patients at risk</span></div>
          <div><b className="crit">{icuAtRisk || liveBlast.critical_patients}</b><span>ICU beds lit</span></div>
          <div><b className="warn">{liveBlast.estimated_harm_minutes}m</b><span>time to harm</span></div>
        </div>
      )}

      <div className="twin-hud twin-legend">
        <span><i className="dot safe" />Bed nominal</span>
        <span><i className="dot warn" />Workflow affected</span>
        <span><i className="dot crit" />ICU monitoring lost</span>
        <span><i className="ring" />Live service</span>
      </div>

      {!touched && (
        <div className="twin-hud twin-hint">
          <Hand size={14} /> Drag to orbit · pinch or scroll to zoom · two fingers or right-drag to pan · click a ward to fly in
        </div>
      )}
    </div>
  );
}
