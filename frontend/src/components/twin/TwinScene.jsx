import { memo, useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Html, Line, Grid, Sparkles, OrbitControls } from '@react-three/drei';
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing';
import * as THREE from 'three';
import { COLORS, HOME_VIEW, INFRA_Y, SERVICE_LABELS, floorY, seeded } from './layout';

const reveal = (anim, t, delay) => {
  if (anim.revealAt == null) return 0;
  return THREE.MathUtils.clamp((t - anim.revealAt - delay) / 0.7, 0, 1);
};

const wardDelay = (floor) => 0.9 + floor * 0.35;

// Where the pointer is inside the canvas; the tooltip is drawn as HTML over the canvas there.
const screenOf = (e) => [e.nativeEvent.offsetX, e.nativeEvent.offsetY];

// ── Camera rig: fly to a focus point, hand control back on user input ──
function CameraRig({ focus }) {
  const { camera, controls } = useThree();
  const flying = useRef(false);
  const target = useMemo(() => new THREE.Vector3(), []);
  const position = useMemo(() => new THREE.Vector3(), []);

  useEffect(() => {
    if (!focus) return;
    target.set(...focus.target);
    position.set(...focus.position);
    flying.current = true;
  }, [focus, target, position]);

  useEffect(() => {
    if (!controls) return;
    const stop = () => { flying.current = false; };
    controls.addEventListener('start', stop);
    return () => controls.removeEventListener('start', stop);
  }, [controls]);

  useFrame((_, dt) => {
    if (!flying.current || !controls) return;
    const k = 1 - Math.exp(-3.2 * dt);
    controls.target.lerp(target, k);
    camera.position.lerp(position, k);
    controls.update();
    if (camera.position.distanceTo(position) < 0.02) flying.current = false;
  });
  return null;
}

// ── Hospital floor: glass slab, wards, beds ──
function Floor({ floor, layout, impact, anim, onHover, onWardClick }) {
  const group = useRef();
  const wards = layout.wards.filter((w) => w.floor === floor);
  const outline = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(layout.slab.width, 0.06, layout.slab.depth)),
    [layout.slab.width, layout.slab.depth]
  );

  useFrame(() => {
    if (group.current) group.current.position.y = floorY(floor, anim.current.explode);
  });

  return (
    <group ref={group}>
      <mesh position={[0, -0.05, 0]}>
        <boxGeometry args={[layout.slab.width, 0.06, layout.slab.depth]} />
        <meshPhysicalMaterial color={COLORS.slab} transparent opacity={0.07} roughness={0.15} metalness={0.1} />
      </mesh>
      <lineSegments position={[0, -0.05, 0]} geometry={outline}>
        <lineBasicMaterial color="#3b6fa8" transparent opacity={0.55} />
      </lineSegments>
      <Html position={[-layout.slab.width / 2 - 0.35, 0.05, layout.slab.depth / 2]} center distanceFactor={13} zIndexRange={[5, 0]} pointerEvents="none">
        <div className="twin-floor-label">L{floor}</div>
      </Html>
      {wards.map((w) => (
        <Ward key={w.id} ward={w} impact={impact} anim={anim} onHover={onHover} onWardClick={onWardClick} />
      ))}
    </group>
  );
}

function Ward({ ward, impact, anim, onHover, onWardClick }) {
  const level = impact.active ? impact.wardLevel[ward.id] : undefined;
  const zoneMat = useRef();
  const critMat = useRef();
  const warnMat = useRef();
  const beams = useRef();
  const critRef = useRef();
  const warnRef = useRef();
  const idleRef = useRef();
  const beamGeo = useMemo(() => {
    const g = new THREE.CylinderGeometry(0.022, 0.05, 1.1, 8, 1, true);
    g.translate(0, 0.55, 0); // grow upward from the bed
    return g;
  }, []);

  const { critical, warning, idle } = useMemo(() => {
    const out = { critical: [], warning: [], idle: [] };
    const generalCount = impact.active ? (impact.generalBeds[ward.id] || 0) : 0;
    ward.beds.forEach((b, i) => {
      const icu = impact.active ? impact.icuBeds[`${ward.id}:${b.id}`] : undefined;
      if (icu) out.critical.push({ ...b, info: icu });
      else if (i < generalCount) out.warning.push(b);
      else out.idle.push(b);
    });
    return out;
  }, [ward, impact]);

  useLayoutEffect(() => {
    const m = new THREE.Matrix4();
    const place = (ref, beds, y = 0.05) => {
      if (!ref.current) return;
      beds.forEach((b, i) => { m.makeTranslation(ward.x + b.x, y, ward.z + b.z); ref.current.setMatrixAt(i, m); });
      ref.current.instanceMatrix.needsUpdate = true;
    };
    place(critRef, critical);
    place(warnRef, warning);
    place(idleRef, idle);
    place(beams, critical, 0.05);
  }, [ward, critical, warning, idle]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const r = reveal(anim.current, t, wardDelay(ward.floor));
    const pulse = 0.65 + 0.35 * Math.sin(t * 4 + ward.x);
    if (zoneMat.current) {
      zoneMat.current.emissiveIntensity = level ? r * (level === 'critical' ? 0.9 : 0.5) * pulse : 0.08;
      zoneMat.current.opacity = level ? 0.18 + 0.32 * r : 0.16;
    }
    if (critMat.current) critMat.current.emissiveIntensity = 0.2 + r * 2.6 * pulse;
    if (warnMat.current) warnMat.current.emissiveIntensity = 0.15 + r * 1.3 * pulse;
    if (beams.current) beams.current.scale.y = Math.max(0.001, r * (0.85 + 0.15 * Math.sin(t * 6)));
  });

  const zoneColor = level === 'critical' ? COLORS.critical : level === 'warning' ? COLORS.warning : COLORS.primary;
  const hover = (kind) => (e) => {
    e.stopPropagation();
    const bed = kind === 'critical' ? critical[e.instanceId] : kind === 'warning' ? warning[e.instanceId] : idle[e.instanceId];
    if (bed) onHover({ kind: 'bed', level: kind, ward, bed, screen: screenOf(e) });
  };

  return (
    <group>
      <mesh
        position={[ward.x, 0.0, ward.z]}
        onClick={(e) => { e.stopPropagation(); onWardClick(ward); }}
        onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer'; onHover({ kind: 'ward', ward, level, screen: screenOf(e) }); }}
        onPointerOut={() => { document.body.style.cursor = ''; onHover(null); }}
      >
        <boxGeometry args={[ward.width, 0.03, ward.depth]} />
        <meshStandardMaterial ref={zoneMat} color={zoneColor} emissive={zoneColor} transparent opacity={0.16} />
      </mesh>

      {idle.length > 0 && (
        <instancedMesh ref={idleRef} args={[null, null, idle.length]} onPointerOver={hover('idle')} onPointerOut={() => onHover(null)}>
          <boxGeometry args={[0.2, 0.07, 0.26]} />
          <meshStandardMaterial color={COLORS.safeDim} emissive={COLORS.safe} emissiveIntensity={0.25} />
        </instancedMesh>
      )}
      {warning.length > 0 && (
        <instancedMesh ref={warnRef} args={[null, null, warning.length]} onPointerOver={hover('warning')} onPointerOut={() => onHover(null)}>
          <boxGeometry args={[0.2, 0.08, 0.26]} />
          <meshStandardMaterial ref={warnMat} color={COLORS.warning} emissive={COLORS.warning} emissiveIntensity={0.2} toneMapped={false} />
        </instancedMesh>
      )}
      {critical.length > 0 && (
        <>
          <instancedMesh ref={critRef} args={[null, null, critical.length]} onPointerOver={hover('critical')} onPointerOut={() => onHover(null)}>
            <boxGeometry args={[0.22, 0.1, 0.28]} />
            <meshStandardMaterial ref={critMat} color={COLORS.critical} emissive={COLORS.critical} emissiveIntensity={0.3} toneMapped={false} />
          </instancedMesh>
          <instancedMesh ref={beams} args={[beamGeo, null, critical.length]} raycast={() => null}>
            <meshBasicMaterial color={COLORS.critical} transparent opacity={0.55} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
          </instancedMesh>
        </>
      )}

      <Html position={[ward.x, 0.32, ward.z - ward.depth / 2]} center distanceFactor={14} zIndexRange={[6, 0]} pointerEvents="none">
        <div className={`twin-ward-label ${level || ''}`}>
          <span>{ward.name}</span>
          {level === 'critical' && <b>{critical.length} ICU</b>}
          {level === 'warning' && <b>{warning.length} beds</b>}
        </div>
      </Html>
    </group>
  );
}

// ── Infrastructure layer ──
function ServiceNode({ id, position, state, probe, anim, onHover }) {
  const core = useRef();
  const shell = useRef();
  const color = state === 'failing' ? COLORS.critical : state === 'cascade' ? COLORS.warning : COLORS.safe;

  useFrame((s, dt) => {
    const t = s.clock.elapsedTime;
    if (shell.current) { shell.current.rotation.y += dt * 0.6; shell.current.rotation.x += dt * 0.25; }
    if (core.current) {
      const p = state === 'failing' ? 1 + 0.18 * Math.sin(t * 6) : 1 + 0.04 * Math.sin(t * 1.5 + position[0]);
      core.current.scale.setScalar(p);
      core.current.material.emissiveIntensity = state === 'failing' ? 2.2 + Math.sin(t * 6) : state === 'cascade' ? 1.4 : 0.9;
    }
  });

  return (
    <group position={position}>
      <mesh
        ref={core}
        onPointerOver={(e) => { e.stopPropagation(); onHover({ kind: 'service', id, probe, state, screen: screenOf(e) }); }}
        onPointerOut={() => onHover(null)}
      >
        <icosahedronGeometry args={[0.32, 1]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1} toneMapped={false} flatShading />
      </mesh>
      <mesh ref={shell} raycast={() => null}>
        <icosahedronGeometry args={[0.55, 1]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.35} />
      </mesh>
      {state === 'failing' && <Shockwave anim={anim} />}
      <Html position={[0, -0.8, 0]} center distanceFactor={15} zIndexRange={[6, 0]} pointerEvents="none">
        <div className={`twin-service-label ${state}`}>
          <span>{SERVICE_LABELS[id] || id}</span>
          {probe && <b>{Math.round(probe.median_latency_ms)} ms · {Math.round(probe.error_rate * 100)}% err</b>}
        </div>
      </Html>
    </group>
  );
}

function Shockwave({ anim }) {
  const group = useRef();
  useFrame((s) => {
    const t = s.clock.elapsedTime - (anim.current.revealAt ?? 0);
    group.current?.children.forEach((ring, i) => {
      const phase = ((t + i * 0.8) % 2.4) / 2.4;
      ring.scale.setScalar(0.6 + phase * 9);
      ring.material.opacity = (1 - phase) * 0.7;
    });
  });
  return (
    <group ref={group}>
      {[0, 1, 2].map((i) => (
        <mesh key={i} rotation={[-Math.PI / 2, 0, 0]} raycast={() => null}>
          <ringGeometry args={[0.92, 1, 96]} />
          <meshBasicMaterial color={COLORS.critical} transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
      ))}
    </group>
  );
}

// Curve from a service node up into a ward; recomputed while floors explode.
function Feed({ from, ward, level, anim, index }) {
  const line = useRef();
  const dots = useRef();
  const curve = useMemo(() => new THREE.QuadraticBezierCurve3(new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()), []);
  const last = useRef(-1);
  const count = level === 'critical' ? 7 : level === 'warning' ? 5 : 3;
  const color = level === 'critical' ? COLORS.critical : level === 'warning' ? COLORS.warning : COLORS.safe;
  const speed = level === 'critical' ? 0.55 : level === 'warning' ? 0.4 : 0.16;
  const tmp = useMemo(() => new THREE.Matrix4(), []);
  const initial = useMemo(() => [from, [ward.x, 0, ward.z]], [from, ward]);

  useFrame((s) => {
    const e = anim.current.explode;
    const y = floorY(ward.floor, e);
    if (Math.abs(e - last.current) > 1e-4) {
      last.current = e;
      curve.v0.set(...from);
      curve.v2.set(ward.x, y, ward.z);
      curve.v1.set((from[0] + ward.x) / 2, Math.max(from[1], y) - 0.2 + 1.2, (from[2] + ward.z) / 2 + 1.4);
      if (line.current) {
        const pts = curve.getPoints(40).flatMap((p) => [p.x, p.y, p.z]);
        line.current.geometry.setPositions(pts);
      }
    }
    if (dots.current) {
      const t = s.clock.elapsedTime;
      const r = level ? reveal(anim.current, t, 0.2) : 1;
      for (let i = 0; i < count; i++) {
        const u = (t * speed + i / count + seeded(index) ) % 1;
        const p = curve.getPoint(level ? Math.min(u, r) : u);
        tmp.makeTranslation(p.x, p.y, p.z);
        dots.current.setMatrixAt(i, tmp);
      }
      dots.current.instanceMatrix.needsUpdate = true;
    }
  });

  return (
    <>
      <Line
        ref={line}
        points={initial}
        color={color}
        lineWidth={level === 'critical' ? 2.2 : level ? 1.6 : 1}
        transparent
        opacity={level === 'critical' ? 0.85 : level ? 0.6 : 0.16}
        toneMapped={false}
      />
      <instancedMesh ref={dots} args={[null, null, count]} raycast={() => null}>
        <sphereGeometry args={[level ? 0.06 : 0.04, 10, 10]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </instancedMesh>
    </>
  );
}

function ServiceEdge({ a, b, hot }) {
  const points = useMemo(() => {
    const c = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...a),
      new THREE.Vector3((a[0] + b[0]) / 2, INFRA_Y - 0.9, (a[2] + b[2]) / 2 + 0.6),
      new THREE.Vector3(...b),
    );
    return c.getPoints(30);
  }, [a, b]);
  return (
    <Line points={points} color={hot ? COLORS.critical : COLORS.violet} lineWidth={hot ? 2 : 1.2}
      transparent opacity={hot ? 0.9 : 0.45} dashed dashScale={6} toneMapped={false} />
  );
}

// Auto-rotate unless the pointer rests on something (read from a ref so hovering never re-renders the scene).
function AutoRotate({ enabled, pausedRef }) {
  useFrame((state) => {
    if (state.controls) state.controls.autoRotate = enabled && !pausedRef.current;
  });
  return null;
}

// Zoom out on narrow (portrait) canvases so the whole hospital stays in frame.
function FitToAspect() {
  useFrame((state) => {
    const zoom = Math.min(1, state.size.width / state.size.height / 1.1);
    if (Math.abs(state.camera.zoom - zoom) > 1e-3) {
      state.camera.zoom = zoom;
      state.camera.updateProjectionMatrix();
    }
  });
  return null;
}

function TwinScene({
  layout, impact, feeds, servicePos, failingService, health, explode, revealKey,
  autoRotate, pausedRef, focus, onHover, onWardClick,
}) {
  // Shared animation clock: floor explode amount and when the blast reveal started.
  const anim = useRef({ explode: 0, revealAt: null, pendingReveal: false });
  useEffect(() => {
    anim.current.pendingReveal = Boolean(revealKey);
    if (!revealKey) anim.current.revealAt = null;
  }, [revealKey]);
  useFrame((state, dt) => {
    const a = anim.current;
    a.explode = THREE.MathUtils.damp(a.explode, explode ? 1 : 0, 3.5, dt);
    if (a.pendingReveal) {
      a.revealAt = state.clock.elapsedTime;
      a.pendingReveal = false;
    }
  });

  const probes = useMemo(() => Object.fromEntries((health || []).map((h) => [h.service, h])), [health]);

  const serviceState = (id) => {
    if (id === failingService || (!failingService && impact.unhealthy.has(id))) return 'failing';
    if (impact.active && impact.cascade.has(id)) return 'cascade';
    return 'healthy';
  };

  return (
    <>
      <color attach="background" args={['#04070c']} />
      <fog attach="fog" args={['#04070c', 16, 38]} />
      <ambientLight intensity={0.35} />
      <directionalLight position={[6, 12, 8]} intensity={0.8} color="#cfe3ff" />
      <pointLight position={[0, INFRA_Y + 1, 2]} intensity={failingService ? 18 : 6} color={failingService ? COLORS.critical : COLORS.primary} distance={14} />

      <CameraRig focus={focus} />

      {layout.floors.map((f) => (
        <Floor key={f} floor={f} layout={layout} impact={impact} anim={anim} onHover={onHover} onWardClick={onWardClick} />
      ))}

      {Object.entries(servicePos).map(([id, pos]) => (
        <ServiceNode key={id} id={id} position={pos} state={serviceState(id)} probe={probes[id]} anim={anim} onHover={onHover} />
      ))}

      {Object.entries(feeds).flatMap(([svc, wardIds], si) =>
        wardIds.filter((w) => layout.wardsById[w] && servicePos[svc]).map((w, wi) => {
          const st = serviceState(svc);
          const level = st === 'failing' ? (impact.active ? impact.wardLevel[w] || 'warning' : 'critical')
            : st === 'cascade' ? 'warning' : undefined;
          return <Feed key={`${svc}-${w}`} index={si * 10 + wi} from={servicePos[svc]} ward={layout.wardsById[w]} level={level} anim={anim} />;
        })
      )}

      {impact.edges.map((e) => servicePos[e.source] && servicePos[e.target] && (
        <ServiceEdge key={`${e.source}-${e.target}`} a={servicePos[e.source]} b={servicePos[e.target]} hot={e.source === failingService} />
      ))}

      <AutoRotate enabled={autoRotate} pausedRef={pausedRef} />
      <FitToAspect />

      <Grid position={[0, INFRA_Y - 0.6, 0]} args={[60, 60]} cellSize={0.6} cellThickness={0.6} cellColor="#0f2a40"
        sectionSize={3} sectionThickness={1.1} sectionColor="#1d5a8a" fadeDistance={30} fadeStrength={1.6} infiniteGrid />
      <Sparkles count={70} scale={[16, 10, 12]} position={[0, 2, 0]} size={2.2} speed={0.25} opacity={0.5} color={COLORS.primary} />

      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        autoRotateSpeed={0.45}
        minDistance={3}
        maxDistance={30}
        maxPolarAngle={Math.PI * 0.62}
        target={HOME_VIEW.target}
      />

      <EffectComposer multisampling={0}>
        <Bloom mipmapBlur intensity={1.15} luminanceThreshold={0.22} luminanceSmoothing={0.35} />
        <Vignette eskil={false} offset={0.2} darkness={0.75} />
      </EffectComposer>
    </>
  );
}

export default memo(TwinScene);
