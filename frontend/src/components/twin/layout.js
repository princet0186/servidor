// Turns the hospital facility + service maps into 3D positions and per-ward impact.

export const HOME_VIEW = { target: [0, 1.4, 0.6], position: [12.5, 8.2, 15.5] };
export const EXPLODED_VIEW = { target: [0, 4.4, 0.6], position: [16.5, 12.5, 21] };
export const FLOOR_GAP = 1.5;
export const EXPLODED_GAP = 2.9;
export const INFRA_Y = -2.2;
const BED_SPACING = 0.34;
const WARD_GAP = 0.55;
const PAD = 0.32;

export const COLORS = {
  safe: '#2fd39a',
  safeDim: '#1d6b55',
  warning: '#ffb35c',
  critical: '#ff3b4f',
  primary: '#9ecaff',
  violet: '#b9a7ff',
  slab: '#7fb4ff',
};

export const SERVICE_LABELS = {
  'vitals-ingestion-svc': 'Vitals Ingestion',
  'medication-alerts-svc': 'Medication Alerts',
  'lab-routing-svc': 'Lab Routing',
  'patient-portal-svc': 'Patient Portal',
};

export function floorY(floor, explode) {
  return floor * (FLOOR_GAP + (EXPLODED_GAP - FLOOR_GAP) * explode);
}

function bedIds(ward) {
  if (Array.isArray(ward.beds)) return ward.beds.map((b) => b.bed_id);
  return Array.from({ length: ward.bed_count || 0 }, (_, i) => `${ward.ward_id}-${i + 1}`);
}

export function buildLayout(facility) {
  const wards = (facility?.wards || []).map((w) => {
    const ids = bedIds(w);
    const n = ids.length;
    const cols = w.type === 'critical_care' ? Math.max(2, Math.ceil(n / 2)) : Math.ceil(Math.sqrt(n * 2.4));
    const rows = Math.max(1, Math.ceil(n / cols));
    const width = cols * BED_SPACING + PAD * 2;
    const depth = rows * BED_SPACING + PAD * 2;
    const beds = ids.map((id, i) => ({
      id,
      x: -width / 2 + PAD + BED_SPACING * (i % cols) + BED_SPACING / 2,
      z: -depth / 2 + PAD + BED_SPACING * Math.floor(i / cols) + BED_SPACING / 2,
    }));
    return { id: w.ward_id, name: w.name, floor: w.floor, type: w.type, specialty: w.specialty, width, depth, beds };
  });

  const floors = [...new Set(wards.map((w) => w.floor))].sort((a, b) => a - b);
  let slabWidth = 0;
  let slabDepth = 0;
  for (const f of floors) {
    const row = wards.filter((w) => w.floor === f);
    const total = row.reduce((s, w) => s + w.width, 0) + WARD_GAP * (row.length - 1);
    let x = -total / 2;
    for (const w of row) {
      w.x = x + w.width / 2;
      w.z = 0;
      x += w.width + WARD_GAP;
      slabDepth = Math.max(slabDepth, w.depth);
    }
    slabWidth = Math.max(slabWidth, total);
  }

  return {
    floors,
    wards,
    wardsById: Object.fromEntries(wards.map((w) => [w.id, w])),
    slab: { width: slabWidth + 1.4, depth: slabDepth + 1.4 },
    topFloor: floors.length ? floors[floors.length - 1] : 0,
  };
}

export function servicePositions(keys) {
  // A shallow arc in front of and below the building: the "infrastructure layer".
  const n = keys.length;
  return Object.fromEntries(keys.map((k, i) => {
    const t = n === 1 ? 0 : i / (n - 1) - 0.5;
    return [k, [t * 7.8, INFRA_Y, 1.8 - Math.abs(t) * 1.4]];
  }));
}

// Which wards each service feeds, from the service -> patient map.
export function serviceFeeds(servicesMap) {
  const feeds = {};
  for (const [svc, ctx] of Object.entries(servicesMap || {})) {
    const wards = new Set();
    (ctx.icu_locations || []).forEach((l) => wards.add(l.ward));
    (ctx.general_wards_affected || []).forEach((w) => wards.add(w.ward));
    feeds[svc] = [...wards];
  }
  return feeds;
}

export function computeImpact({ blast, failingService, graph, health }) {
  const icuBeds = {};
  (blast?.icu_locations || []).forEach((l) => { icuBeds[`${l.ward}:${l.bed}`] = l; });
  const generalBeds = {};
  (blast?.general_wards || []).forEach((w) => { generalBeds[w.ward] = w.beds_affected || 0; });

  const wardLevel = {};
  Object.keys(icuBeds).forEach((k) => { wardLevel[k.split(':')[0]] = 'critical'; });
  Object.keys(generalBeds).forEach((w) => { if (!wardLevel[w]) wardLevel[w] = 'warning'; });

  const cascade = new Set(
    (graph?.edges || []).filter((e) => e.source === failingService).map((e) => e.target)
  );
  const unhealthy = new Set((health || []).filter((h) => h.status !== 'healthy').map((h) => h.service));
  if (failingService) unhealthy.add(failingService);

  return { icuBeds, generalBeds, wardLevel, cascade, unhealthy, edges: graph?.edges || [], active: Boolean(blast) };
}

// Deterministic jitter so renders stay pure.
export function seeded(i) {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}
