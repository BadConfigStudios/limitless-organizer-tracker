export type DateWindow = "" | "30" | "90" | "180";

export function dateWindowToDays(dateWindow: DateWindow): number | undefined {
  return dateWindow === "" ? undefined : Number(dateWindow);
}

export function filterByDateWindow<T>(
  items: T[],
  getDate: (item: T) => string,
  days: DateWindow,
): T[] {
  if (days === "") return items;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - Number(days));
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  return items.filter((item) => getDate(item) >= cutoffStr);
}
