export function formatPrepTime(minutes) {
  if (minutes === null || minutes === undefined || Number.isNaN(Number(minutes))) {
    return "N/A";
  }

  const total = Math.max(0, Math.floor(Number(minutes)));
  if (total < 60) {
    return `${total} min`;
  }

  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (mins === 0) {
    return `${hours}h`;
  }
  return `${hours}h ${mins}m`;
}
