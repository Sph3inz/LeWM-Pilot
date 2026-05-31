/** Local East-North-Up helpers for telemetry → 3D view. */

const M_PER_FT = 0.3048;
const EARTH_RADIUS_M = 6378137;

export function ftToM(ft: number): number {
  return ft * M_PER_FT;
}

export function latLonToEnuM(
  lat: number,
  lon: number,
  originLat: number,
  originLon: number
): { east: number; north: number } {
  const originLatRad = (originLat * Math.PI) / 180;
  const dLat = ((lat - originLat) * Math.PI) / 180;
  const dLon = ((lon - originLon) * Math.PI) / 180;
  return {
    north: dLat * EARTH_RADIUS_M,
    east: dLon * EARTH_RADIUS_M * Math.cos(originLatRad)
  };
}

export function hasGeoFix(lat: number | null | undefined, lon: number | null | undefined): boolean {
  return lat != null && lon != null && Number.isFinite(lat) && Number.isFinite(lon);
}
