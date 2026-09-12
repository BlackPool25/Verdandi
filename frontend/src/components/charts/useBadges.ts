import { useSyncExternalStore } from "react";
import type { BadgeSnapshot, TwinStore } from "../../store/twinStore";

export function useBadges(store: TwinStore): BadgeSnapshot {
  return useSyncExternalStore(
    (notify) => store.subscribeBadges(notify),
    () => store.badges(),
    () => store.badges(),
  );
}
