import { DiagnosisLoader } from "../components/diagnosis/DiagnosisLoader";
import decidedFixture from "../test/fixtures/diagnosis-seed777.json";
import abstainFixture from "../test/fixtures/diagnosis-abstain.json";

const decidedPacket = (decidedFixture as { packet: unknown }).packet;
const decidedDecision = (decidedFixture as { decision: unknown }).decision;
const abstainPacket = (abstainFixture as { packet: unknown }).packet;
const abstainDecision = (abstainFixture as { decision: unknown }).decision;

export function DiagnosisDemo(): React.JSX.Element {
  return (
    <div>
      <section className="sim-box px-panel" data-testid="demo-diagnosis-decided">
        <h2>Diagnosis — decided (seed 777)</h2>
        <DiagnosisLoader packetJson={decidedPacket} decisionJson={decidedDecision} />
      </section>
      <section className="sim-box px-panel" data-testid="demo-diagnosis-abstain">
        <h2>Diagnosis — abstain (clean seed 777)</h2>
        <DiagnosisLoader packetJson={abstainPacket} decisionJson={abstainDecision} />
      </section>
    </div>
  );
}
