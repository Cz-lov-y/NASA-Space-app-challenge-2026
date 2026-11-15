/** Shared map and legend colors. */
export const SIGNAL_COLORS = {
  supported_signal: '#dc2626',
  uncertain_signal: '#eab308',
  no_detected_divergence: '#16a34a',
  pending: '#64748b',
} as const;
export function signalColor(status?: string): string {
  return SIGNAL_COLORS[status as keyof typeof SIGNAL_COLORS] || SIGNAL_COLORS.pending;
}
