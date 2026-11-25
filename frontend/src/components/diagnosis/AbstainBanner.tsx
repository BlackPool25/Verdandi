// Task 9 abstain banner: the only render for abstained packets.
// Zero chips, zero buttons, zero selectors: static text only.
export interface AbstainBannerProps {
  readonly packetId: string | null;
  readonly reason?: string | undefined;
  readonly coverageSummary?: string | null | undefined;
}

export function AbstainBanner({
  packetId,
  reason,
  coverageSummary,
}: AbstainBannerProps): React.JSX.Element | null {
  return (
    <section aria-label="diagnosis abstain" data-testid="diagnosis-abstain" className="sim-box px-panel">
      <div className="causal-card__header">
        <span className="causal-card__tag">DIAGNOSIS</span>
        <span className="px-badge">ABSTAIN</span>
      </div>
      <p className="causal-card__claim" data-testid="diagnosis-abstain-reason">
        collect more evidence{reason ? ` — ${reason}` : ""}
      </p>
      <p className="path-note" data-testid="diagnosis-abstain-packet">
        packet {packetId ?? "unknown packet"}
      </p>
      {coverageSummary ? (
        <p className="path-note" data-testid="diagnosis-abstain-coverage">
          coverage {coverageSummary}
        </p>
      ) : null}
    </section>
  );
}
