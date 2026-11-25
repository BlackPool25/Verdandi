// Task 9 parse gate + pure builders (mirrors `src/reporter.py`).
// Validators never throw: malformed input returns null. Builders copy
// numbers verbatim and drop uncited claims instead of asserting.
import type {
  DiagnosisCardData,
  DiagnosisDecision,
  DiagnosisDossier,
  DiagnosisPacket,
  EvidencePath,
  EvidenceTrace,
} from "./types";

function isRecord(u: unknown): u is Record<string, unknown> {
  return typeof u === "object" && u !== null && !Array.isArray(u);
}

function optString(u: unknown): string | null {
  return typeof u === "string" ? u : null;
}

function optNumber(u: unknown): number | null {
  return typeof u === "number" && Number.isFinite(u) ? u : null;
}

function numberRecord(u: unknown): Readonly<Record<string, number>> {
  if (!isRecord(u)) return {};
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(u)) {
    if (typeof v === "number" && Number.isFinite(v)) out[k] = v;
  }
  return out;
}

function parseTrace(u: unknown): EvidenceTrace | null {
  try {
    if (!isRecord(u)) return null;
    const id = optString(u["id"]);
    const machine = optString(u["machine"]);
    const onset = optNumber(u["onset"]);
    if (id === null || machine === null || onset === null) return null;
    const kind = optString(u["onset_kind"]);
    const own = optString(u["own_state"]);
    const hop = optNumber(u["hop_est"]);
    const ev = optString(u["evidence"]);
    return {
      id,
      machine,
      onset,
      onset_kind: kind ?? undefined,
      own_state: own ?? undefined,
      hop_est: hop ?? undefined,
      evidence: ev ?? undefined,
    };
  } catch {
    return null;
  }
}

function parsePath(u: unknown): EvidencePath | null {
  try {
    if (!isRecord(u)) return null;
    const id = optString(u["id"]);
    if (id === null || !Array.isArray(u["nodes"])) return null;
    const nodes: string[] = [];
    for (const n of u["nodes"]) {
      if (typeof n !== "string") return null;
      nodes.push(n);
    }
    const prob = optNumber(u["prob"]);
    if (prob === null) return null;
    return { id, nodes, prob };
  } catch {
    return null;
  }
}

/** Unknown -> packet. Null on malformed (never throws). */
export function parseDiagnosisPacket(u: unknown): DiagnosisPacket | null {
  try {
    if (!isRecord(u)) return null;
    const id = optString(u["id"]);
    if (id === null) return null;
    const trigger = optNumber(u["trigger"]);
    if (trigger === null) return null;
    const sensor = optString(u["sensor_verdict"]);
    if (sensor === null) return null;
    const verdict = optString(u["verdict"]);
    if (verdict === null) return null;
    const rootRaw = u["root"];
    const root = rootRaw === null || rootRaw === undefined ? null : optString(rootRaw);
    if (rootRaw !== null && rootRaw !== undefined && root === null) return null;
    const onsetRaw = u["onset"];
    const onset = onsetRaw === null || onsetRaw === undefined ? null : optNumber(onsetRaw);
    if (onsetRaw !== null && onsetRaw !== undefined && onset === null) return null;
    const familyRaw = u["fault_family"];
    const faultFamily =
      familyRaw === null || familyRaw === undefined ? null : optString(familyRaw);
    if (familyRaw !== null && familyRaw !== undefined && faultFamily === null) return null;
    const traceRaw = u["trace"];
    const pathsRaw = u["paths"];
    if (!Array.isArray(traceRaw) || !Array.isArray(pathsRaw)) return null;
    const trace: EvidenceTrace[] = [];
    for (const t of traceRaw) {
      const row = parseTrace(t);
      if (row === null) return null;
      trace.push(row);
    }
    const paths: EvidencePath[] = [];
    for (const p of pathsRaw) {
      const row = parsePath(p);
      if (row === null) return null;
      paths.push(row);
    }
    const kindRaw = u["onset_kind"];
    const ownRaw = u["own_state"];
    return {
      id,
      root,
      onset,
      trigger,
      sensor_verdict: sensor,
      fault_family: faultFamily,
      verdict,
      onset_kind: kindRaw === undefined ? undefined : optString(kindRaw),
      own_state: ownRaw === undefined ? undefined : optString(ownRaw),
      trace,
      paths,
      confidence: numberRecord(u["confidence"]),
      flow: isRecord(u["flow"]) ? u["flow"] : {},
    };
  } catch {
    return null;
  }
}

/** Unknown -> decision. Null on malformed (never throws). */
export function parseDiagnosisDecision(u: unknown): DiagnosisDecision | null {
  try {
    if (!isRecord(u)) return null;
    const verdictRaw = u["verdict"];
    if (verdictRaw !== undefined && typeof verdictRaw !== "string") return null;
    const getStr = (k: string): string | null | undefined => {
      const v = u[k];
      if (v === undefined) return undefined;
      if (v === null) return null;
      return typeof v === "string" ? v : null;
    };
    const getNum = (k: string): number | null | undefined => {
      const v = u[k];
      if (v === undefined) return undefined;
      if (v === null) return null;
      return typeof v === "number" && Number.isFinite(v) ? v : null;
    };
    if (getStr("machine") === null && u["machine"] !== null) return null;
    const spec = optString(u["spec"]);
    const packetId = optString(u["packet_id"]);
    const machine = getStr("machine");
    const machineProb = getNum("machine_prob");
    const family = getStr("fault_family");
    const familyProb = getNum("fault_family_prob");
    const templateProb = getNum("family_prob");
    const severity = getStr("severity");
    const severityProb = getNum("severity_prob");
    return {
      spec: spec ?? undefined,
      packet_id: packetId ?? undefined,
      machine,
      machine_prob: machineProb,
      fault_family: family,
      fault_family_prob: familyProb,
      family_prob: templateProb,
      severity,
      severity_prob: severityProb,
      verdict: typeof verdictRaw === "string" ? verdictRaw : undefined,
    };
  } catch {
    return null;
  }
}

/** Packet id universe (mirror of reporter `_ids`): packet + trace + paths. */
export function diagnosisIdUniverse(packet: DiagnosisPacket): Set<string> {
  const ids = new Set<string>([packet.id]);
  for (const t of packet.trace) ids.add(t.id);
  for (const p of packet.paths) ids.add(p.id);
  return ids;
}

/** Pure card builder (mirror of `build_card`): abstain when either side
 *  abstains; decided claims copy verbatim, uncited claims dropped. */
export function buildCardView(
  packet: DiagnosisPacket,
  decision: DiagnosisDecision,
): DiagnosisCardData {
  if (decision.verdict === "abstain" || packet.verdict === "abstain") {
    return {
      verdict: "abstain",
      root: null,
      severity: null,
      packet_id: packet.id,
      claims: [],
      action: "collect more evidence",
    };
  }
  const trace0 = packet.trace[0];
  const path0 = packet.paths[0];
  const valid = diagnosisIdUniverse(packet);
  const candidates: ReadonlyArray<{
    readonly text: string;
    readonly value: unknown;
    readonly evidence_id: string | undefined;
  }> = [
    { text: "origin", value: decision.machine ?? packet.root, evidence_id: trace0?.id },
    { text: "onset", value: trace0?.onset, evidence_id: trace0?.id },
    { text: "causal path", value: path0?.nodes, evidence_id: path0?.id },
  ];
  const claims = candidates
    .filter((c) => c.evidence_id !== undefined && valid.has(c.evidence_id))
    .map((c) => ({
      text: c.text,
      value: c.value,
      evidence_id: c.evidence_id as string,
    }));
  const top1 = packet.confidence["top1"];
  return {
    verdict: "decided",
    root: decision.machine ?? packet.root,
    fault_family: decision.fault_family ?? packet.fault_family,
    severity: decision.severity ?? null,
    confidence: top1 ?? null,
    machine_prob: decision.machine_prob ?? null,
    packet_id: packet.id,
    claims,
    action: "inspect root machine",
  };
}

/** Pure dossier builder (mirror of `build_dossier`): all IDs intact. */
export function buildDossierView(
  packet: DiagnosisPacket,
  decision: DiagnosisDecision,
): DiagnosisDossier {
  return {
    packet_id: packet.id,
    decision,
    nodes: packet.trace.map((t) => ({
      machine: t.machine,
      onset: t.onset,
      onset_kind: t.onset_kind ?? null,
      evidence_id: t.id,
    })),
    paths: packet.paths.map((p) => ({ id: p.id, nodes: [...p.nodes], prob: p.prob })),
    confidence: { ...packet.confidence },
    flow: { ...packet.flow },
    verdict: decision.verdict ?? packet.verdict,
  };
}
