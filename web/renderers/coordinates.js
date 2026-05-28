export function physicsNormalToThreeComponents(normal) {
  const vector = { x: normal.x, y: normal.z, z: normal.y };
  const length = Math.hypot(vector.x, vector.y, vector.z);
  if (length === 0) {
    return { x: 0, y: 1, z: 0 };
  }
  return { x: vector.x / length, y: vector.y / length, z: vector.z / length };
}

export function formatThreeNormal(components) {
  return [components.x, components.y, components.z]
    .map((component) => (Math.abs(component) < 1e-9 ? 0 : component))
    .map((component) => Number(component.toFixed(6)).toString())
    .join(",");
}
