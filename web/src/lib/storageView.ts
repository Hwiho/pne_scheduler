import type { StorageRecord } from "./api";

export type StorageFilter = "current" | "active" | "attention" | "completed" | "archived" | "all";

export function storageNeedsAttention(record: StorageRecord, now: number): boolean {
  return !record.archivedAt && !record.completedAt && record.alerts.some((alert) =>
    !alert.acknowledgedAt && Date.parse(alert.snoozedUntil ?? alert.dueAt) <= now,
  );
}

export function filterStorageRecords(records: StorageRecord[], query: string, filter: StorageFilter, now: number): StorageRecord[] {
  const normalize = (value: string) => value.normalize("NFKC").toLocaleLowerCase("ko-KR");
  const needle = normalize(query.trim());
  return records.filter((record) => {
    if (needle && !normalize(`${record.sample} ${record.id}`).includes(needle)) return false;
    if (filter === "all") return true;
    if (filter === "archived") return !!record.archivedAt;
    if (record.archivedAt) return false;
    if (filter === "active") return !record.completedAt;
    if (filter === "completed") return !!record.completedAt;
    if (filter === "attention") return storageNeedsAttention(record, now);
    return true;
  });
}
