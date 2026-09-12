import { EventFeed } from "./EventFeed";
import type { TwinEvent } from "./types";

export interface MachineEventFeedProps {
  readonly events: readonly TwinEvent[];
  readonly machineId: string;
  readonly cap?: number | undefined;
}

/** Per-machine feed: thin pin of the global feed to one machine id. */
export function MachineEventFeed(props: MachineEventFeedProps): React.JSX.Element {
  return <EventFeed events={props.events} machineId={props.machineId} cap={props.cap} />;
}
