// Task 9 diagnosis packet/card/dossier mirrors (frozen python shapes).
// No logic here: parse.ts validates, builders mirror src/reporter.py.

/** One ranked candidate row: per-machine evidence, id `ev-{machine}`. */
export interface EvidenceTrace {
  readonly id: string;
  readonly machine: string;
  readonly onset: number;
  readonly onset_kind?: string | undefined;
  readonly own_state?: string | undefined;
  readonly hop_est?: number | undefined;
  readonly evidence?: string | undefined;
}

/** One ranked propagation path, id `path-{i}`. */
export interface EvidencePath {
  readonly id: string;
  readonly nodes: readonly string[];
  readonly prob: number;
}

/** Mirror of `emit_packet` schema v1 (`src/packet.py`). */
export interface DiagnosisPacket {
  readonly id: string;
  readonly root: string | null;
  readonly onset: number | null;
  readonly trigger: number;
  readonly sensor_verdict: string;
  readonly fault_family: string | null;
  readonly verdict: string;
  readonly onset_kind?: string | null | undefined;
  readonly own_state?: string | null | undefined;
  readonly trace: readonly EvidenceTrace[];
  readonly paths: readonly EvidencePath[];
  readonly confidence: Readonly<Record<string, number>>;
  readonly flow: Readonly<Record<string, unknown>>;
}

/** Mirror of `decide` / template decision (`src/jev.py`, template path). */
export interface DiagnosisDecision {
  readonly spec?: string | undefined;
  readonly packet_id?: string | undefined;
  readonly machine?: string | null | undefined;
  readonly machine_prob?: number | null | undefined;
  readonly fault_family?: string | null | undefined;
  readonly fault_family_prob?: number | null | undefined;
  readonly family_prob?: number | null | undefined;
  readonly severity?: string | null | undefined;
  readonly severity_prob?: number | null | undefined;
  readonly verdict?: string | undefined;
}

/** One operator claim: value copied verbatim, cited by evidence id. */
export interface DiagnosisClaim {
  readonly text: string;
  readonly value: unknown;
  readonly evidence_id: string;
}

/** Mirror of `build_card` (`src/reporter.py`). */
export interface DiagnosisCardData {
  readonly verdict: string;
  readonly root: string | null;
  readonly fault_family?: string | null | undefined;
  readonly severity: string | null;
  readonly confidence?: number | null | undefined;
  readonly machine_prob?: number | null | undefined;
  readonly packet_id: string | null;
  readonly claims: readonly DiagnosisClaim[];
  readonly action: string;
}

/** One dossier node: full trace row with its evidence id. */
export interface DiagnosisDossierNode {
  readonly machine: string;
  readonly onset: number;
  readonly onset_kind?: string | null | undefined;
  readonly evidence_id: string;
}

/** Mirror of `build_dossier` (`src/reporter.py`). */
export interface DiagnosisDossier {
  readonly packet_id: string | null;
  readonly decision: DiagnosisDecision;
  readonly nodes: readonly DiagnosisDossierNode[];
  readonly paths: readonly EvidencePath[];
  readonly confidence: Readonly<Record<string, number>>;
  readonly flow: Readonly<Record<string, unknown>>;
  readonly verdict: string | null;
}
