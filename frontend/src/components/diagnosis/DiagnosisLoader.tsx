// Task 9 artifact loader + parse gate. Memoized parse only: no store
// subscription, no effect, no fetch. Default-off: null in / null out.
import { useMemo } from "react";
import type { DiagnosisCardData, DiagnosisDossier } from "./types";
import {
  buildCardView,
  buildDossierView,
  parseDiagnosisDecision,
  parseDiagnosisPacket,
} from "./parse";
import { AbstainBanner } from "./AbstainBanner";
import { DiagnosisCard } from "./DiagnosisCard";
import { DossierView } from "./DossierView";

export interface DiagnosisLoaderProps {
  readonly packetJson: unknown;
  readonly decisionJson: unknown;
  readonly selectedId?: string | undefined;
  readonly onSelect?: ((id: string) => void) | undefined;
  readonly onStepTo?: ((step: number) => void) | undefined;
}

export function DiagnosisLoader({
  packetJson,
  decisionJson,
  selectedId,
  onSelect,
  onStepTo,
}: DiagnosisLoaderProps): React.JSX.Element | null {
  const parsed = useMemo(() => {
    const packet = parseDiagnosisPacket(packetJson);
    if (packet === null) return null;
    const decision = parseDiagnosisDecision(decisionJson) ?? { verdict: packet.verdict };
    const card: DiagnosisCardData = buildCardView(packet, decision);
    const dossier: DiagnosisDossier = buildDossierView(packet, decision);
    return { packet, decision, card, dossier };
  }, [packetJson, decisionJson]);
  // Default-off: no artifact wired yet renders nothing (no abstain noise,
  // no tick-path work). Malformed or abstained artifacts abstain honestly.
  if (packetJson === null || packetJson === undefined) return null;
  if (parsed === null) {
    return <AbstainBanner packetId={null} reason="unparseable packet" />;
  }
  const abstained =
    parsed.decision.verdict === "abstain" || parsed.packet.verdict === "abstain";
  if (abstained || parsed.card.verdict === "abstain") {
    const top1 = parsed.packet.confidence["top1"];
    const tau = parsed.packet.confidence["tau"];
    const coverage =
      top1 !== undefined && tau !== undefined
        ? `conf ${top1} tau ${tau}`
        : top1 !== undefined
          ? `conf ${top1}`
          : "no coverage estimate";
    return (
      <AbstainBanner
        packetId={parsed.packet.id}
        reason="empty evidence trace"
        coverageSummary={coverage}
      />
    );
  }
  return (
    <>
      <DiagnosisCard
        card={parsed.card}
        packet={parsed.packet}
        onSelect={onSelect}
        onStepTo={onStepTo}
        selectedId={selectedId}
      />
      <DossierView
        dossier={parsed.dossier}
        packet={parsed.packet}
        onSelect={onSelect}
        onStepTo={onStepTo}
      />
    </>
  );
}
