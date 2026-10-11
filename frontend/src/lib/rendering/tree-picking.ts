/** Screen-space tolerance improves picking, not inventory completeness. */
export function nearestTree<T extends { geometry: { type: string; coordinates?: unknown }; properties?: Record<string, unknown> | null }>(
  features: T[], point: { x: number; y: number }, project: (coordinate: [number, number]) => { x: number; y: number }, radius = 9,
): T | undefined {
  let nearest: T | undefined, distance = radius * radius;
  for (const feature of features) {
    if (feature.geometry.type !== 'Point' || feature.properties?.point_count != null) continue;
    const pixel = project(feature.geometry.coordinates as [number, number]);
    const squared = (pixel.x - point.x) ** 2 + (pixel.y - point.y) ** 2;
    if (squared <= distance) { nearest = feature; distance = squared; }
  }
  return nearest;
}
