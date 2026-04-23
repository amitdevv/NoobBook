export function patchOne<T extends { id: string }>(
  items: T[],
  id: string,
  updater: Partial<T> | ((item: T) => T)
): T[] {
  return items.map((item) => {
    if (item.id !== id) return item;
    return typeof updater === 'function'
      ? updater(item)
      : { ...item, ...updater };
  });
}

export function upsertOne<T extends { id: string }>(
  items: T[],
  nextItem: T,
  options?: { prepend?: boolean }
): T[] {
  const existingIndex = items.findIndex((item) => item.id === nextItem.id);
  if (existingIndex === -1) {
    return options?.prepend ? [nextItem, ...items] : [...items, nextItem];
  }

  return items.map((item) => (item.id === nextItem.id ? nextItem : item));
}

export function removeOne<T extends { id: string }>(items: T[], id: string): T[] {
  return items.filter((item) => item.id !== id);
}
