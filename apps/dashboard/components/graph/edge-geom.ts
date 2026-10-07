export type Rect = { x: number; y: number; w: number; h: number };

export function edgeGeometry(a: Rect, b: Rect, laneIndexA: number, laneIndexB: number) {
  let p0: number[];
  let p3: number[];
  let c1: number[];
  let c2: number[];
  if (laneIndexA === laneIndexB) {
    p0 = [a.x, a.y + a.h / 2];
    p3 = [b.x, b.y + b.h / 2];
    const off = 10 + Math.min(8, Math.abs(p3[1] - p0[1]) / 30);
    c1 = [p0[0] - off, p0[1]];
    c2 = [p3[0] - off, p3[1]];
  } else if (laneIndexA < laneIndexB) {
    p0 = [a.x + a.w, a.y + a.h / 2];
    p3 = [b.x, b.y + b.h / 2];
    const dx = Math.max(24, (p3[0] - p0[0]) * 0.5);
    c1 = [p0[0] + dx, p0[1]];
    c2 = [p3[0] - dx, p3[1]];
  } else {
    p0 = [a.x, a.y + a.h / 2];
    p3 = [b.x + b.w, b.y + b.h / 2];
    const dx = Math.max(24, (p0[0] - p3[0]) * 0.5);
    c1 = [p0[0] - dx, p0[1]];
    c2 = [p3[0] + dx, p3[1]];
  }
  const t = 0.5;
  const bz = (i: number) =>
    (1 - t) ** 3 * p0[i] +
    3 * (1 - t) ** 2 * t * c1[i] +
    3 * (1 - t) * t ** 2 * c2[i] +
    t ** 3 * p3[i];
  return {
    d: `M ${p0[0]} ${p0[1]} C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${p3[0]} ${p3[1]}`,
    mid: [bz(0), bz(1)] as [number, number],
  };
}
