// The API sends UTC timestamps without a zone suffix ("2026-10-24T09:30:00").
// Parse them as UTC; a bare ISO string would otherwise be read as local time.
export function parseServerTime(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  const s = String(value);
  return new Date(/Z|[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`);
}
