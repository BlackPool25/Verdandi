import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import decidedFixture from "./fixtures/diagnosis-seed777.json";
import abstainFixture from "./fixtures/diagnosis-abstain.json";
import {
  buildCardView,
  buildDossierView,
  parseDiagnosisDecision,
  parseDiagnosisPacket,
} from "../components/diagnosis/parse";
import { DiagnosisLoader } from "../components/diagnosis/DiagnosisLoader";

// Task 9 failing-first: recorded fixtures only (emit_packet verbatim via
// scripts/report_incident.py run_report(seed=777)); never hand-written.
const DECIDED_PACKET = (decidedFixture as { packet: unknown }).packet;
const DECIDED_DECISION = (decidedFixture as { decision: unknown }).decision;
const ABSTAIN_PACKET = (abstainFixture as { packet: unknown }).packet;
const ABSTAIN_DECISION = (abstainFixture as { decision: unknown }).decision;

function renderLoader(packetJson: unknown, decisionJson: unknown): string {
  return renderToStaticMarkup(createElement(DiagnosisLoader, { packetJson, decisionJson }));
}

function chipIds(html: string): string[] {
  const out: string[] = [];
  const re = /data-testid="diagnosis-chip-([^"]+)"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) {
    const id = m[1];
    if (id !== undefined) out.push(id);
  }
  return out;
}

function packetIdUniverse(packet: unknown): Set<string> {
  const p = packet as {
    id?: unknown;
    trace?: ReadonlyArray<{ id?: unknown }>;
    paths?: ReadonlyArray<{ id?: unknown }>;
  };
  const ids = new Set<string>();
  if (typeof p.id === "string") ids.add(p.id);
  for (const t of p.trace ?? []) if (typeof t.id === "string") ids.add(t.id);
  for (const q of p.paths ?? []) if (typeof q.id === "string") ids.add(q.id);
  return ids;
}

describe("diagnosis panels (Task 9)", () => {
  it("chip IDs are a subset of the packet ID universe (no uncited chips)", () => {
    const packet = parseDiagnosisPacket(DECIDED_PACKET);
    const decision = parseDiagnosisDecision(DECIDED_DECISION);
    expect(packet).not.toBeNull();
    expect(decision).not.toBeNull();
    if (packet === null || decision === null) throw new Error("fixture must parse");
    const card = buildCardView(packet, decision);
    const dossier = buildDossierView(packet, decision);
    expect(card.verdict).toBe("decided");
    expect(card.claims.length).toBeGreaterThan(0);
    const html = renderLoader(DECIDED_PACKET, DECIDED_DECISION);
    const chips = chipIds(html);
    expect(chips.length).toBeGreaterThan(0);
    const universe = packetIdUniverse(DECIDED_PACKET);
    for (const chip of chips) {
      expect(universe.has(chip)).toBe(true);
    }
    // Node + path rows cite packet trace/path IDs too.
    expect(html).toContain("diagnosis-node-ev-A0");
    expect(html).toContain("diagnosis-path-path-0");
    expect(dossier.nodes.length).toBe(packet.trace.length);
  });

  it("abstain renders zero chips with reason + coverage (no selectors)", () => {
    const html = renderLoader(ABSTAIN_PACKET, ABSTAIN_DECISION);
    expect(html).toContain("diagnosis-abstain");
    expect(html).toContain("collect more evidence");
    expect(html).toContain("det-777-190");
    expect(chipIds(html)).toEqual([]);
    expect(html).not.toContain("diagnosis-node-");
    expect(html).not.toContain("diagnosis-path-");
    expect(html).not.toContain("<button");
    expect(html).toContain("diagnosis-abstain-coverage");
  });

  it("abstain banner shows packet confidence verbatim when present", () => {
    const html = renderLoader(DECIDED_PACKET, { verdict: "abstain" });
    expect(html).toContain("diagnosis-abstain");
    expect(html).toContain("collect more evidence");
    expect(html).toContain("det-777-190");
    expect(html).toContain("conf 0.940342449817933");
    expect(html).toContain("tau 0.739");
    expect(chipIds(html)).toEqual([]);
    expect(html).not.toContain("<button");
  });

  it("same JSON renders the same HTML (deterministic, no stale state)", () => {
    const first = renderLoader(DECIDED_PACKET, DECIDED_DECISION);
    const second = renderLoader(
      JSON.parse(JSON.stringify(DECIDED_PACKET)),
      JSON.parse(JSON.stringify(DECIDED_DECISION)),
    );
    expect(second).toBe(first);
  });

  it("malformed input abstains without throwing", () => {
    expect(parseDiagnosisPacket({})).toBeNull();
    expect(parseDiagnosisPacket(null)).toBeNull();
    expect(parseDiagnosisPacket("packet")).toBeNull();
    expect(parseDiagnosisPacket(42)).toBeNull();
    expect(parseDiagnosisDecision(undefined)).toBeNull();
    const html = renderLoader({}, null);
    expect(html).toContain("diagnosis-abstain");
    expect(html).not.toContain("<button");
    expect(chipIds(html)).toEqual([]);
  });
});
