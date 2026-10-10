# MDA — Model-Driven Architecture for Verdandi

Three levels, computation-independent to platform-specific. Each level has an
intro, Mermaid diagrams, and a mapping back to repo files. Numbers are pinned
to `PLAN.md`, `docs/SIM_SPEC.md`, `docs/ARCHITECTURE.md`, and `src/config.py`;
nothing here invents metrics.

## 1. CIM (Computation-Independent Model)

The business problem, from `ELENCHUS_DISCOVERY.md`: a student team needs a
ranked causal trace plus a why-explanation for every factory-twin alarm,
because detectors alone force 30-60min of hand triage and unverifiable
stories lose viva marks. No software concepts appear at this level.

### 1.1 Context

Operators, the plant historian, the maintenance crew, and viva examiners
surround Verdandi. Alarms flow in, ranked traces with replay proof flow out.
The safety-restart decision stays human; the twin never issues clearance.

```mermaid
flowchart LR
    OP["Operators"] --> V["Verdandi boundary"]
    PH["Plant historian"] --> V
    MC["Maintenance crew"] --> V
    VE["Viva examiners"] --> V
    V --> RT["Ranked trace plus replay proof"]
    V --> WE["Why-explanation"]
    HD["Human safety decision"] -. "stays outside" .-> V
```

Maps to: `ELENCHUS_DISCOVERY.md` sections 1-2 (persona, stakeholders),
`docs/SIM_SPEC.md` section 13.2 (actuation boundary).

### 1.2 Domain model

Business entities only. No code types, no tables, no services.

```mermaid
classDiagram
    class Machine {
        name
        role
        operating state
    }
    class Buffer {
        name
        level
        capacity
    }
    class Part {
        identity
        quality flag
    }
    class FaultWindow {
        start step
        end step
        fault family
    }
    class Alarm {
        alarmed machine
        window
        detector reading
    }
    class RankCause {
        ranked machines
        top-one accuracy
    }
    class Explanation {
        sentences
        grounding rate
    }
    class Replay {
        seed
        subgraph
        diverge flag
    }
    Machine "1" --> "*" Buffer : feeds
    Part --> Machine : visits
    FaultWindow --> "*" Machine : touches
    Alarm --> FaultWindow : raised inside
    RankCause --> Alarm : answers
    Explanation --> RankCause : justifies
    Replay --> RankCause : proves
```

Maps to: `docs/ARCHITECTURE.md` data contracts (`Alarm`, `RankCause`,
`Explanation`, `Replay`), `docs/SIM_SPEC.md` sections 2 and 5 (plant,
fault taxonomy).

### 1.3 Business process

Today an alarm means 30-60min of hand triage. With Verdandi it means a
ranked trace plus a why-explanation plus replay proof, straight away.

```mermaid
flowchart TD
    A["Factory alarm"] --> B{"Triage path"}
    B --> C["Hand triage today"]
    C --> D["Fix after 30 to 60 minutes"]
    B --> E["Ranked trace"]
    E --> F["Why-explanation"]
    F --> G["Replay proof"]
    G --> H["Fix at root cause"]
```

Maps to: `ELENCHUS_DISCOVERY.md` POV line and HMWs, `PLAN.md` verified goal.

## 2. PIM (Platform-Independent Model)

The design from `docs/SDD.md` and `docs/ARCHITECTURE.md`, with no platform
types: no Python, no TypeScript, no SimPy, no Parquet. Components expose
abstract operations; data shapes are logical, not serialized.

### 2.1 Structural view

Seven logical components. Abstract operations end with `*`.

```mermaid
classDiagram
    class Twin {
        runEpisode()*
        injectFault()*
        readTick()*
    }
    class Detector {
        calibrate()*
        score()*
        raiseAlarm()*
    }
    class Veto {
        applyMask()*
    }
    class Walk {
        walkUpstream()*
        pruneTopK()*
    }
    class Narrator {
        narrate()*
        fallbackCards()*
    }
    class Verifier {
        checkTriples()*
        groundingRate()*
    }
    class ReplayHarness {
        replaySubgraph()*
        assertZeroDiverge()*
    }
    class TrailExporter {
        exportTrail()*
    }
    Twin --> Detector : ticks
    Detector --> Veto : scored alarms
    Veto --> Walk : vetoed candidates
    Walk --> Narrator : ranked causes
    Narrator --> Verifier : sentences
    Verifier --> ReplayHarness : grounded text
    ReplayHarness --> TrailExporter : replay proof
```

Maps to: `docs/SDD.md` section 2.2 module specs, `docs/ARCHITECTURE.md`
pipeline (`Twin -> Detect -> Veto-mask -> Walk -> Narrate+Verify ->
Replay -> UI + trail`).

### 2.2 Interaction view

One alarm travelling the full chain, including the fallback branch.

```mermaid
sequenceDiagram
    participant A as AlarmSource
    participant D as Detector
    participant V as Veto
    participant W as Walk
    participant R as RankCause
    participant N as Narrator
    participant VF as Verifier
    participant E as Explanation
    A->>D: alarm with window
    D->>V: scored alarms
    V->>W: vetoed candidates
    W->>R: ranked machines with edge ids
    R->>N: RankCause
    N->>VF: sentences with triples
    alt grounded and within deadline
        VF->>E: verified Explanation
    else tail or ungrounded
        VF->>E: chain-card fallback
    end
```

Maps to: `docs/SDD.md` sequence diagram, `docs/ARCHITECTURE.md` narrate
step (8s deadline, K3 5% rule).

### 2.3 Behavioral view

Machine states plus the fallback chain as an activity flow.

```mermaid
stateDiagram-v2
    [*] --> RUN
    RUN --> STARVED : upstream empty
    RUN --> BLOCKED : downstream full
    RUN --> DOWN : breakdown
    STARVED --> RUN : parts arrive
    BLOCKED --> RUN : downstream drains
    DOWN --> RUN : repair done
```

```mermaid
flowchart TD
    D["Detect"] --> V["Veto"]
    V --> W["Walk"]
    W --> N["Narrate"]
    N --> VF{"Verify"}
    VF --> OK["Grounded explanation"]
    VF --> FB["Chain-cards fallback"]
    FB --> RP["Replay"]
    OK --> RP
```

Machine states map to `docs/SIM_SPEC.md` section 8 channel 5
(`RUN`, `BLOCKED`, `STARVED`, `DOWN`). The chain maps to
`docs/ARCHITECTURE.md` steps 2-7 and quality scenarios S2 (8s deadline)
and S4 (0-diverge).

## 3. PSM (Platform-Specific Model)

Concrete technology from the repo: SimPy twin, FastAPI SSE bridge, React
plus Zustand viewer, Parquet offline store. No SQL database exists. CPU-only.

### 3.1 Technical structural view

```mermaid
classDiagram
    class TwinEngine {
        simpy Environment
        simpy Resource AGV
        simpy Store buffers
        run_episode()
    }
    class DetectorJob {
        numpy quantile
        IQR mask
        score_windows()
    }
    class BridgeApp {
        fastapi FastAPI
        sse-starlette stream
        replay_ticks()
    }
    class ViewerStore {
        zustand store
        xyflow graph
        setAlarm()
        setTrace()
    }
    class DatasetFiles {
        pyarrow parquet
        pydantic schema v6
        export_episode()
    }
    TwinEngine --> DetectorJob : ticks
    DetectorJob --> BridgeApp : alarms JSON
    BridgeApp --> ViewerStore : SSE frames
    TwinEngine --> DatasetFiles : episode records
    DatasetFiles --> DetectorJob : calibration window
```

Maps to: `src/twin.py` and `src/config.py` (twin), `services/sim_bridge/app.py`
and `sse.py` (bridge), `frontend/` with `zustand` and `@xyflow/react`
(`frontend/package.json`), `src/dataset_export.py` (Parquet export).

### 3.2 Data model

Parquet files, not Postgres. One row per tick, one header per episode,
stratification keys per record.

```mermaid
erDiagram
    EPISODES ||--o{ TICKS : contains
    EPISODES {
        int seed
        int T
        string code_version
        int schema_version
    }
    TICKS {
        int step
        float obs
        string state
        int throughput
        float current
        int buffers
    }
    EPISODES ||--o{ STRATKEYS : labels
    STRATKEYS {
        string family
        string mode
        string root_id
        int hop
        float wear_endpoint
    }
    TICKS ||--o{ WINDOWFEATURES : aggregates
    WINDOWFEATURES {
        int cal_win
        int warmup_steps
        float threshold_qdet
    }
```

Pins: `T=300`, `CAL_WIN=120`, `WARMUP_STEPS=15`, `TWIN_SCHEMA=6`,
`CODE_VERSION=twin-2.5.0-topology-A` (`src/config.py`); 26 machines and 26
buffers (topology-A roster); 182-row manifest is 26 machines x 7 fault
classes (`docs/SIM_SPEC.md`); tick keys frozen in
`services/sim_bridge/SCHEMA.md`. Channel 9 energy is header-only, channel
10 air is on probation (`docs/SIM_SPEC.md` section 8).

### 3.3 Deployment view

One laptop CPU node, two containers, one shared volume, SSE transport,
600s wall budget.

```mermaid
flowchart LR
    LP["Laptop CPU node"] --> API["api service on port 8000"]
    LP --> WEB["web service on port 19104"]
    API --> VOL["artifacts volume"]
    WEB --> VOL
    API --> SSE["SSE tick stream"]
    SSE --> WEB
    WB["Wall budget under 600s"] -. "guards" .-> API
```

Maps to: `compose.yaml` (`api` + `web` services, `verdandi-artifacts`
volume), `.env` (`WEB_PORT=19104`, `API_PORT=8000`), `scripts/check_gates.py`
(`--max-s` default 600.0).

## 4. Mapping matrix

| Model Type | CIM | PIM | PSM |
|---|---|---|---|
| Context | Section 1.1 context diagram, `ELENCHUS_DISCOVERY.md` | Pipeline logical flow, `docs/SDD.md` | Section 3.3 deployment flowchart, `compose.yaml` |
| Structural | Section 1.2 domain model, business attributes only | Section 2.1 components with abstract operations | Section 3.1 SimPy, FastAPI, Zustand, Parquet types |
| Interaction | Section 1.3 alarm-to-proof process | Section 2.2 alarm chain sequence | SSE tick frames, `services/sim_bridge/SCHEMA.md` |
| Behavioral | 30-60min triage versus ranked trace | Section 2.3 machine states plus fallback chain | Wall budget and 0-diverge gates, `scripts/check_gates.py` |
