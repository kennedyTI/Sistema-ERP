export function buildApiUrl(path: string) {
  const configuredBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
  const normalizedPath = path.replace(/^\/+/, "");

  if (!configuredBase) return `/api/${normalizedPath}`;
  if (configuredBase.endsWith("/api")) return `${configuredBase}/${normalizedPath}`;
  return `${configuredBase}/api/${normalizedPath}`;
}
