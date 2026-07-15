export const MAX_RESOURCES = 10;
export const MAX_RESOURCE_BYTES = 20 * 1024 * 1024;
export const MAX_TEMPLATE_BYTES = 15 * 1024 * 1024;

export function formatMb(bytes: number): number {
  return bytes / (1024 * 1024);
}
