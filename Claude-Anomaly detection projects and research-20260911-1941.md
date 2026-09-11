# Anomaly detection projects and research

**Created:** 9/11/2026 8:17:49  
**Updated:** 9/11/2026 13:53:48  
**Exported:** 9/11/2026 19:41:08  
**Link:** [https://claude.ai/chat/b481fae0-391d-4ae8-8b94-fbabfd2a19f9](https://claude.ai/chat/b481fae0-391d-4ae8-8b94-fbabfd2a19f9)  

## User:

> 9/11/2026 8:17:50

I want you research across lots and lots of online websites and project showcase sites and GitHub and I want you to find me the absolute best projects unique and innovative projects and latest technology projects in anamoly detection. Software only. Ask me if you have any questions before the research

I want to do a simulation kinda project in which we have some kind of factory running in digital twin kinda mode and then it there is an anamoly I want it to actually trace back all the issues and actually fine the entire trace in way explaining why what happened rather than just detecting
I have amd 7900gre and I'm good at python but I'm fine if we are going to use rust for performance too

## Assistant:

> 9/11/2026 8:18:00

> Preparing clarifying questions before starting research.
>
> - Preparing clarifying questions before starting research.
> - **Done**

## User:

> 9/11/2026 8:19:12

Q: What's the main goal for this project?
A: it's a semester projects. and we will use ai to help us build so do not base it on old timelines. cause ai will make prototyping and building very fast so I don't want a project that can just be built in a day

Q: What kind of factory/process do you want to simulate?
A: IoT sensor network (temp, vibration, pressure)

Q: For root-cause tracing, any approach you're drawn to?
A: Not sure - recommend based on research

## Assistant:

> 9/11/2026 8:20:33

> Researching causal digital twin frameworks for industrial security datasets.
>
> - Planning an ambitious semester project on an IoT sensor digital twin.
> - digital twin anomaly detection root cause analysis GitHub 2026
> - Researching causal digital twin frameworks for industrial security datasets.
> - SWaT WADI dataset industrial control system anomaly detection benchmark github
> - PyRCA RCAEval root cause analysis library python github microservices
> - causal discovery python library Tigramite causal-learn time series 2026
> - **Done**

Now let me look at digital twin simulation frameworks for IoT/factory sensors, GNN fault diagnosis, and check ROCm/AMD GPU relevance.

> Searched the web
>
> - open source digital twin simulator IoT sensor factory python simpy github
> - **Done**

Good coverage. Let me check GNN-based fault diagnosis / trace explanation approaches and LLM-agent based RCA (relevant given "explain why" requirement), plus explore AMD ROCm PyTorch status for this kind of workload.

> Checking GPU compatibility and regional availability details.
>
> - graph neural network fault propagation explanation industrial anomaly LLM agent explainable trace 2026
> - Surveying relevant graph-based anomaly detection research.
> - AMD 7900 GRE ROCm PyTorch support 2026 machine learning
> - Checking GPU compatibility and regional availability details.
> - **Done**

Good news — this space is very active right now, and there's a clean gap you can fill for a semester project: most anomaly detection work stops at *"this metric is off"* or *"here's the anomalous node,"* and only a handful of very recent (2025-2026) papers push into causal, narrated root-cause tracing. That's your opening.

**Prior art worth knowing (so you don't rebuild it from scratch)**

- **Causal Digital Twin (CDT)** — Sept 2025 arXiv paper combining causal inference with a digital twin for ICS security. It supports association for pattern detection, intervention for system response, and counterfactual analysis for attack prevention, and reports 74% fewer false positives with 78.4% root-cause accuracy on SWaT/WADI/HAI. Code is public. This is close to what you're describing — read it closely.
- **RCAEval** (phamquiluan, FSE'26/WWW'25) — an open benchmark with nine datasets, 735 real failure cases, and 15 reproducible RCA baselines covering metric, trace, and multi-source methods. Good for evaluation methodology even if you don't reuse the microservice domain.
- **PyRCA** (Salesforce) — a Python ML library offering state-of-the-art RCA algorithms and an end-to-end pipeline, including causal-graph construction from time series and domain knowledge.
- **GDN / graph deviation networks + XGNNs** — GNN message-passing captures how variables influence one another, producing topology-aware representations that reflect real fault propagation, and can assign importance scores during inference. Explanations from these models map directly onto process diagrams — the alarm and its physical trail shown together. This is basically "trace visualization" for free.
- **IstGPT** (2026) — an LLM- and graph-learning based industrial anomaly detector that builds interpretable spatial-temporal graphs, using an LLM pipeline to extract sensor-actuator dependencies and iteratively validate graph structure. Very close to "explain what happened," not just detect.
- **Graph-Augmented Multi-Agent RCA** (2026, AIOps) — uses multiple LLM agents cross-checking hypotheses against "Golden Signals" for consistency and checking whether a proposed root cause sufficiently explains the propagation chain, beating pure graph-GNN baselines like DeepTraLog.
- **Causal-TS** (July 2026) — brand new library with GPU-accelerated conditional-independence testing and nonstationarity-aware causal discovery, built on top of Tigramite/causal-learn/DoWhy ideas — worth using instead of writing PC/PCMCI from scratch.

**Datasets for realism/validation:** SWaT and WADI are the standard ICS benchmarks — SWaT has 42 sensors/actuators across six stages with 36 attacks over 11 days, WADI has 123 devices across three subsystems with 15 attacks over 16 days. You'd need to request access via iTrust, but they're the credibility anchor reviewers/professors recognize.

**Simulators for the digital twin layer:** SimPy-based twins exist (discrete-event, MIT license), and dedicated IIoT simulators like fillol's **IIoT-simulator** already model three production lines (pressing, welding, painting) publishing vibration, temperature, and quality sensor data over MQTT with configurable QoS to a control center with predictive alert logic — good reference architecture even if you build your own.

**What would make this an actual semester-scale project (not a weekend one):**
1. **Digital twin**: SimPy or a custom discrete-event engine simulating a multi-stage line with realistic physical coupling (e.g., a bearing overheats → vibration rises → downstream part quality drops → jams the next station). The *coupling* is the hard part and the thing that makes root-cause tracing meaningful.
2. **Detection layer**: GNN-based deviation detection (start from GDN-style architectures) over the sensor graph.
3. **Causal structure layer**: Causal discovery (PCMCI/Causal-TS) learned from normal operation to build the "physics" graph the detector and explainer both reason over.
4. **Trace/explanation layer**: this is your differentiator — walk backward through the causal graph from the anomalous node, using timing/lag info from the causal discovery step to reconstruct an actual event sequence, then have an LLM turn that sequence into a narrated explanation ("Bearing 3 vibration crossed threshold at t=110s, which preceded a temperature rise at t=118s, consistent with the causal edge learned from normal operation... this most likely originated from...").
5. **Counterfactual/what-if**: since you already have a simulator, you can *replay* the twin with the suspected root cause fixed and show the anomaly wouldn't have propagated — genuinely differentiates you from anything above.

**Stack**: Python for the ML/causal-discovery/LLM-orchestration layers (PyTorch + PyG for GNNs, Tigramite or Causal-TS for causal discovery). Rust is a good fit for the simulation engine itself if you want it to run many fast Monte Carlo replays for counterfactual testing — that's a legitimate, not gratuitous, use of Rust here.

**On your GPU**: the 7900 GRE isn't on AMD's officially-supported ROCm list, but it shares the same RDNA3 architecture as the 7900 XT/XTX (gfx1100), so ROCm 6.x generally works with `HSA_OVERRIDE_GFX_VERSION=11.0.0` as a workaround. ROCm 6.x supports RDNA3 well enough for inference and fine-tuning of standard architectures — plenty for GNN training and small LLM inference/fine-tuning, which is all this project needs.

Want me to sketch a concrete week-by-week semester plan next, or dig deeper into one layer (e.g., the causal-discovery-to-explanation pipeline)?

---

**Sources:**

- [root-cause-analysis · GitHub Topics · GitHub](https://github.com/topics/root-cause-analysis?l=html)
- [anomaly-detection · GitHub Topics · GitHub](https://github.com/topics/anomaly-detection?after=Y3Vyc29yOjYy&o=desc&s=updated&utf8=%E2%9C%93)
- [(PDF) Causal Digital Twins for cyber-physical security in water systems: A framework for robust anomaly detection](https://www.researchgate.net/publication/398808814_Causal_Digital_Twins_for_cyber-physical_security_in_water_systems_A_framework_for_robust_anomaly_detection)
- [Systems and methods for identifying machine anomaly root cause based on a selected reduced order model and a selected fault model](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11899527)
- [Causal Digital Twins for Cyber-Physical Security: A Framework for Robust Anomaly Detection in Industrial Control Systems](https://arxiv.org/html/2510.09616v1)
- [[2510.09616] Causal Digital Twins for Cyber-Physical Security: A Framework for Robust Anomaly Detection in Industrial Control Systems](https://arxiv.org/abs/2510.09616)
- [Apparatus using root cause analysis for predicting blade damage and method therefor](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12359589)
- [Causal Digital Twins for Cyber-Physical Security in Water Systems: A Framework for Robust Anomaly Detection | Request PDF](https://www.researchgate.net/publication/397506818_Causal_Digital_Twins_for_Cyber-Physical_Security_in_Water_Systems_A_Framework_for_Robust_Anomaly_Detection)
- [The Digital Twin Landscape at the Crossroads of Predictive Maintenance, Machine Learning and Physics Based Modeling](https://arxiv.org/pdf/2206.10462)
- [GitHub - pwwl/ics-anomaly-detection: ICS anomaly detection test suite. From the ESORICS 2022 paper: "Perspectives from a Comprehensive Evaluation of Reconstruction-based Anomaly Detection in Industrial Control Systems"" · GitHub](https://github.com/pwwl/ics-anomaly-detection)
- [GitHub - OliverHennhoefer/awesome-ts-anomaly-detection-datasets: Collection of Time-Series Anomaly Detection Datasets · GitHub](https://github.com/OliverHennhoefer/awesome-ts-anomaly-detection-datasets)
- [GitHub - ngoclesydney/Anomaly-Detection-with-Swat-Dataset: Develope novel security metric using Deep-Learning to detect anomaly attacks into the critical infrastructure systems. This metric will be tested by Secure Water Treatment (SWaT) Dataset.](https://github.com/ngoclesydney/Anomaly-Detection-with-Swat-Dataset)
- [DAICS: A Deep Learning Solution for Anomaly Detection in Industrial Control Systems](https://arxiv.org/pdf/2009.06299)
- [AI-driven real-time anomaly detection in industrial cyber-physical systems using hybrid deep learning with SWaT and WADI benchmarks - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2773186326001295)
- [HCL-MTSAD: Hierarchical Contrastive Consistency Learning for Accurate Detection of Industrial Multivariate Time Series Anomalies](https://arxiv.org/pdf/2404.08224)
- [Graph Anomaly Detection in Time Series: A Survey](https://arxiv.org/pdf/2302.00058)
- [INVARLLM: LLM-assisted Physical Invariant Extraction for Cyber-Physical Systems Anomaly Detection](https://arxiv.org/pdf/2411.10918)
- [awesome-industrial-datasets/markdown/secure_water_treatment__swat__dataset.md at master · jonathanwvd/awesome-industrial-datasets](https://github.com/jonathanwvd/awesome-industrial-datasets/blob/master/markdown/secure_water_treatment__swat__dataset.md)
- [Ti-iLSTM: A TinyDL Approach for Logic-Level Anomaly Detection in Industrial Water Treatment Systems](https://arxiv.org/pdf/2605.15874)
- [GitHub - salesforce/PyRCA: PyRCA: A Python Machine Learning Library for Root Cause Analysis · GitHub](https://github.com/salesforce/PyRCA)
- [PyRCA/README.md at main · salesforce/PyRCA](https://github.com/salesforce/PyRCA/blob/main/README.md)
- [- Introduction](https://github.com/ai4sre/PyRCA)
- [GitHub - phamquiluan/RCAEval: [FSE'26, WWW'25, ASE'24] RCAEval: A Benchmark for Root Cause Analysis. · GitHub](https://github.com/phamquiluan/RCAEval)
- [RCAEval: A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data | Companion Proceedings of the ACM on Web Conference 2025](https://dl.acm.org/doi/10.1145/3701716.3715290)
- [RCAEval: A Benchmark for Root Cause Analysis of Microservice](https://arxiv.org/pdf/2412.17015)
- [PyRCA: A Library for Metric-based Root Cause Analysis | Request PDF](https://www.researchgate.net/publication/371728567_PyRCA_A_Library_for_Metric-based_Root_Cause_Analysis)
- [PyRCA - AI Gateway](https://aigateway.dev/pyrca/)
- [PyRCA: A Python library for Root Cause Analysis](https://pypi.org/project/sfr-pyrca/1.0.1/)
- [GitHub - jakobrunge/tigramite: Tigramite is a python package for causal inference with a focus on time series data. The Tigramite documentation is at · GitHub](https://github.com/jakobrunge/tigramite)
- [GitHub - mbruhns/tigramite: Tigramite is a time series analysis python module for causal discovery. The Tigramite documentation is at](https://github.com/mbruhns/tigramite)
- [tigramite/README.md at master · jakobrunge/tigramite](https://github.com/jakobrunge/tigramite/blob/master/README.md)
- [anaconda.org](https://anaconda.org/cf-post-staging/tigramite)
- [tigramite/tutorials/causal_discovery/tigramite_tutorial_causal_discovery_overview.ipynb at master · jakobrunge/tigramite](https://github.com/jakobrunge/tigramite/blob/master/tutorials/causal_discovery/tigramite_tutorial_causal_discovery_overview.ipynb)
- [Causal-TS: A Python Library for Causal Discoveryin High-Dimensional and Nonstationary Time Series](https://arxiv.org/html/2607.24673)
- [A Python Library for Causal Discovery in High-Dimensional ...](https://arxiv.org/pdf/2607.24673)
- [Causal-TS: A Python Library for Causal Discovery](https://arxiv.org/pdf/2607.24673v1)
- [anaconda.org](https://anaconda.org/channels/cf-post-staging/packages/tigramite/overview)
- [GitHub - doachyz/IIoT-simulator: An advanced Industrial IoT (IIoT) simulator for Smart Factory 4.0 environments using Python, MQTT, and Docker. Emulates configurable production lines with realistic sensor data (vibration, temperature, quality) and predictive alerts. · GitHub](https://github.com/doachyz/IIoT-simulator)
- [GitHub - antonsarg/iot-sensor-data-simulator: An IoT sensor data simulator for generating and transmitting representative IoT sensor data. The project is open source and provides a versatile tool for IoT development and research. · GitHub](https://github.com/antonsarg/iot-sensor-data-simulator)
- [digital-twin · GitHub Topics · GitHub](https://github.com/topics/digital-twin?o=desc&s=updated)
- [GitHub - fillol/IIoT-simulator: An advanced Industrial IoT (IIoT) simulator for Smart Factory 4.0 environments using Python, MQTT, and Docker. Emulates configurable production lines with realistic sensor data (vibration, temperature, quality) and predictive alerts. · GitHub](https://github.com/fillol/IIoT-simulator)
- [simpy · GitHub Topics · GitHub](https://github.com/topics/simpy?o=desc&s=updated)
- [Open-source IP intercom & video surveillance software platform (RBT/Teledom)](https://github.com/topics/smart-buildings)
- [github.com](https://github.com/topics/dtdl)
- [Top Free & Open Source Digital Twin and Plant Simulation Tools - MDCplus](https://mdcplus.fi/blog/top-free-digital-twin-plant-simulation-manufacturing/)
- [Explainable and Fine-Grained Safeguarding of LLM Multi-Agent Systems via Bi-Level Graph Anomaly Detection | Request PDF](https://www.researchgate.net/publication/398979382_Explainable_and_Fine-Grained_Safeguarding_of_LLM_Multi-Agent_Systems_via_Bi-Level_Graph_Anomaly_Detection)
- [Explainable Neural Network meets Graph Neural Network: Recent advances in process fault detection and diagnosis - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0098135425005319)
- [LLM-Guided Measurement Credibility Correction for Trustworthy Industrial Process Inference](https://arxiv.org/pdf/2607.06111)
- [GitHub - flyingdoog/awesome-graph-explainability-papers: Papers about explainability of GNNs · GitHub](https://github.com/flyingdoog/awesome-graph-explainability-papers)
- [Graph Neural Networks with Trainable Adjacency Matrices for Fault Diagnosis on Multivariate Sensor Data](https://arxiv.org/pdf/2210.11164)
- [Agentic and LLM-Based Multimodal Anomaly Detection: Architectures, Challenges, and Prospects](https://www.mdpi.com/1424-8220/26/8/2330)
- [Graph-Augmented Multi-Agent Robust Root Cause Analysis in AIOps - ScienceDirect](https://www.sciencedirect.com/org/science/article/pii/S1546221826005011)
- [IstGPT: LLM-based Anomaly Detection for Spatial-Temporal Graph in Industrial Systems](https://arxiv.org/pdf/2606.01691)
- [Knowledge-graph-enhanced and LLM-guided fault diagnosis for VSC-HVDC systems | AIP Advances | AIP Publishing](https://pubs.aip.org/aip/adv/article/15/11/115330/3373210/Knowledge-graph-enhanced-and-LLM-guided-fault)
- [AMD arms three of its gaming GPUs with PyTorch and ROCm support for AI development | Tom's Hardware](https://www.tomshardware.com/pc-components/gpus/amd-arms-three-of-its-gaming-gpus-with-pytorch-and-rocm-support-for-ai-development)
- [AMD Extends Support for PyTorch Machine Learning Development on Select RDNA™ 3 GPUs with ROCm™ 5.7 – PyTorch](https://pytorch.org/blog/amd-extends-support-for-pt-ml/)
- [AMD Extends PyTorch + ROCm Support To The Radeon RX 7900 XT - Phoronix](https://www.phoronix.com/news/Radeon-RX-7900-XT-ROCm-PyTorch)
- [AMD ROCm Local LLM Setup (2026): 96 tok/s on RX 7900 XTX](https://localaimaster.com/blog/amd-rocm-local-llm-setup)
- [ROCm in 2026: PyTorch on the RX 7900 XTX Still Falls Short — Pickuma](https://pickuma.com/for-dev/rocm-pytorch-rx-7900-xtx-research-2026/)
- [ROCm in 2026: Why PyTorch on the RX 7900 XTX Still Falls Short for Research — Pickuma](https://pickuma.com/for-dev/rocm-pytorch-rx-7900-xtx-research-gaps-2026/)

## User:

> 9/11/2026 8:30:00

Is this actually feasibile and the trace working

## Assistant:

> 9/11/2026 8:30:30

> Weighing causal discovery against a hybrid domain-knowledge approach.
>
> - Weighing causal discovery against a hybrid domain-knowledge approach.
> - **Done**

Yes — feasible, but with one part that's genuinely hard and needs a workaround. Here's the honest breakdown.

**What definitely works:**
- **Simulation layer**: Building a multi-stage line with correlated physical failure modes (bearing wear → vibration → heat → downstream defect) is just careful engineering, not research risk. This is the most time-consuming part but the least uncertain.
- **GNN-based anomaly detection**: Well-trodden ground (GDN and similar). Training on your 7900 GRE via ROCm is fine at this scale — you're talking dozens of sensor nodes, not billions of parameters.
- **LLM narration**: Turning a structured event chain into readable prose is low-risk. This is templating + generation, not the hard science part.
- **Counterfactual replay**: Because you control the simulator, you can literally rerun the twin with the suspected cause patched and check whether the anomaly still propagates. This is actually *easier* in simulation than real industry, where you can't rerun history.

**The genuinely hard part: causal discovery from scratch.**
Algorithms like PCMCI/Causal-TS try to infer the causal graph purely from observational time series, with no prior knowledge of plant structure. In practice this is fragile — sensitive to lag-window choice, struggles with feedback loops and shared common causes, and gets computationally expensive as sensor count grows. If you rely on pure blind causal discovery as your only source of truth, there's a real chance your "trace" points to a statistically plausible but physically wrong chain, and you won't easily know it's wrong.

**The fix (and it's what the strongest recent papers actually do):** don't discover the graph blind. Seed it with the known plant topology — you're building the simulator, so you already know which sensors *can* physically influence which others (conveyor A feeds station B, etc.). Use that as a prior/skeleton graph, then use causal discovery only to learn edge weights, lags, and rule out edges that don't hold up statistically. IstGPT does something similar — extracting sensor-actuator dependencies from domain knowledge first, then refining the graph with the model rather than discovering it from nothing. This turns causal discovery from "the risky unknown" into "a refinement step," which is much safer for a semester timeline.

**How you'll know the trace actually works — this is the part people skip.** Since it's your simulator, you know ground truth: which component you broke and when. Build your evaluation the way RCAEval does it — inject N different fault scenarios, run your trace algorithm, and score whether the true root cause shows up in the top-1/top-3/top-5 candidates (AC@1, AC@3, Avg@5). Without this, "the trace explained something" is just a vibe. With it, you have a number you can put in a report and defend.

**Realistic semester scope**, roughly:
- Weeks 1–4: simulator + fault injection + known-topology graph
- Weeks 4–7: GNN detector + causal refinement on top of the known skeleton
- Weeks 7–10: backward-trace algorithm + counterfactual replay + evaluation harness
- Weeks 10–13: LLM narration layer + demo/UI
- Buffer weeks for the inevitable "the causal edges look wrong" debugging

Net answer: feasible, ambitious-but-right-sized for a semester with AI-assisted coding, and the trace *will* work reliably if you seed the causal graph with known plant structure rather than discovering it blind — that's the one design decision that determines whether this succeeds or turns into a debugging swamp.

## User:

> 9/11/2026 13:45:49

If I give it prior knowledge about the plant structure and connections is it feasible?

## Assistant:

> 9/11/2026 13:46:04

Yes — this is the version that's genuinely low-risk. Once you give the system the plant topology as a prior, causal discovery stops being "find the unknown structure" and becomes "confirm and weight a structure you already know," which is a much easier and more reliable problem. Here's what that actually buys you and what's left to build.

**What prior topology removes as a risk:**
- No more "does an edge exist at all" — you already know conveyor A can only affect station B, not station Z on the other side of the plant. That eliminates the biggest failure mode of blind causal discovery (spurious edges from confounders).
- Feedback loops and common-cause confusion mostly disappear, because you're not inferring direction from correlation alone — you know mechanically which way influence flows.
- Compute drops a lot, because you're only testing conditional independence on the edges your topology says are plausible, not all pairs.

**What's still genuinely left to learn from data (this is your real ML work, not busywork):**
- **Lag/timing**: how many seconds after a vibration spike does temperature actually rise, given your simulator's physics? That's not in the topology — you learn it.
- **Edge strength/weight**: some physically-possible paths matter a lot, others barely propagate signal. You learn which.
- **Anomalous vs. normal propagation**: the same topology behaves differently under fault vs. healthy operation — that difference *is* the anomaly signature the GNN learns.
- **Multi-path disambiguation**: if two sensors both plausibly explain an anomaly and the topology allows both, you still need the data (timing, magnitude, consistency) to rank which one is more likely the true root cause. This is where your evaluation harness (AC@1/AC@3 against ground-truth injected faults) really earns its keep.

**Concrete pipeline now that topology is known:**
1. Build the topology graph by hand from your simulator design (nodes = sensors/actuators, edges = physically possible influence).
2. Run causal discovery *constrained to that skeleton* — this is exactly what algorithms like PCMCI+ support (you give them a prior/forbidden-edges mask), so you're not fighting the library, you're using it as intended.
3. Fit lag + strength per edge from normal-operation simulation data.
4. At anomaly time, walk backward through the weighted graph from the triggering node, using lag-consistency to prune implausible chains (an "effect" at t=100 can't have a "cause" that only shows deviation at t=105).
5. Score candidate chains, rank them, hand the top chain + supporting evidence to the LLM for narration.
6. Validate against injected ground-truth faults.

**One thing to be upfront about for the write-up**: leaning on known topology is a deliberate scope decision — you're not claiming to solve causal discovery from scratch (which is still an open problem), you're claiming that *given* domain knowledge of plant structure (which any real factory has — P&IDs, wiring diagrams), you can reliably reconstruct and explain fault propagation. That's a legitimate, defensible framing for a semester project, and it's honestly closer to how real industrial deployments work anyway — nobody runs blind causal discovery on a plant they already have engineering diagrams for.

So: yes, feasible, and this is the right call. It turns your riskiest unknown into an engineering task instead of a research gamble.

## User:

> 9/11/2026 13:48:35

What's digital twin simulation tool should I use to simulate all this complex factory settings. We are going to use rust or go right for complex fast simulation across lots of different machines efficiently compare to python

## Assistant:

> 9/11/2026 13:49:02

> Evaluating Rust's discrete-event simulation library options.
>
> - Evaluating tools for factory digital twin simulations.
> - Rust discrete event simulation library factory manufacturing 2026
> - Evaluating language options for discrete event simulation tools.
> - Go discrete event simulation library manufacturing factory framework
> - Evaluating Rust's discrete-event simulation library options.
> - **Done**

Let me be straight with you: the honest answer is nuanced, not just "pick this tool."

**Reality check on Rust for this: the ecosystem is thin.** I looked — the Rust DES crates that exist (`sim`/`desru`, RustSim) are small, low-adoption, mostly hobby-scale projects, not batteries-included frameworks like SimPy. You'd essentially be writing your own DES engine in Rust, which is extra scope you don't need for a project already ambitious on the ML side.

**Go is a better fit if you want non-Python performance.** `godes` (MIT, goroutine-based, actively maintained since 2013) and `simgo` are legitimate SimPy-equivalents, and Go's concurrency model — each machine/process as a lightweight goroutine — maps naturally onto discrete-event simulation. It's a much smaller jump than Rust with real speed benefits.

**But here's the question worth asking first: do you actually need the speed?** A factory twin with dozens of sensors running event-driven simulation is not computationally heavy — Python/SimPy handles thousands of events per second without breaking a sweat. The place where raw throughput genuinely matters is your **counterfactual replay validation step** (rerunning the twin hundreds/thousands of times with different suspected root causes patched, to score which explanation holds up). That's embarrassingly parallel and actually performance-bound — a legitimate place to reach for Go or Rust.

**My actual recommendation, split by layer:**

- **Core factory twin (the physics/process model)**: build it in Python on **SimPy**, or better, **FactorySimPy** — a purpose-built manufacturing component library on top of SimPy with pre-built machine/conveyor classes, models the plant as a graph (nodes = processing elements, edges = transport), and explicitly supports both accelerated and real-time modes for digital twin use cases. This gets you the exact topology-as-graph structure you need for the causal layer, and it stays in the same language as your GNN/causal-discovery/LLM code — no serialization boundary, no debugging across languages while you're still figuring out the science.
- **Counterfactual replay engine (the part that's actually parallel and perf-sensitive)**: this is where Go earns its place — spin up `godes` (or even just goroutines around your own lightweight event loop) to run mass parallel replays scoring root-cause hypotheses fast. You could also do this by just running many SimPy instances via Python multiprocessing, which may honestly be good enough — worth prototyping in pure Python first and only reaching for Go if it's demonstrably a bottleneck.
- **Rust**: keep it in your back pocket for one specific hot path if profiling shows Python is the bottleneck (e.g., a tight numeric kernel called millions of times), exposed to Python via PyO3. Don't build the simulator's core loop in Rust from scratch — the ecosystem isn't there to support you and it'll eat weeks you don't have.

**Bottom line**: Python/SimPy (or FactorySimPy) for the twin itself, optionally Go for parallel counterfactual replay if profiling shows you need it, Rust only as a scalpel for a proven bottleneck — not as the foundation. This keeps your semester budget on the actual hard problem (causal tracing + explanation) instead of reimplementing simulation infrastructure that already exists and works well in Python.

---

**Sources:**

- [discrete-event-simulation · GitHub Topics · GitHub](https://github.com/topics/discrete-event-simulation?l=rust&o=asc&s=forks)
- [simul 0.5.1](https://docs.rs/crate/simul/latest/builds/3555646)
- [sim 0.13.1](https://docs.rs/crate/sim/latest/builds/4025127)
- [salabim - discrete event simulation](https://WWW.GITHUB.COM/topics/discrete-event-simulation)
- [state_macros 0.2.0](https://docs.rs/crate/state_macros/latest/source/Cargo.toml)
- [Sim — Rust simulation library // Lib.rs](https://lib.rs/crates/sim)
- [desru 0.1.13](https://docs.rs/crate/desru/latest)
- [RustSim: A Process-Oriented Simulation Framework for the Rust Language | IEEE Conference Publication | IEEE Xplore](https://ieeexplore.ieee.org/document/10408161/)
- [GitHub - ndebuhr/sim: Sim provides a discrete event simulation engine, to facilitate Rust- and npm-based simulation products and projects · GitHub](https://github.com/ndebuhr/sim)
- [Simulation — list of Rust libraries/crates // Lib.rs](https://lib.rs/simulation)
- [pypi.org](https://pypi.org/project/factorysimpy/)
- [pypi.org](https://pypi.org/project/mlafactory/)
- [(PDF) INTEGRATING DISCRETE EVENT SIMULATION WITH ENERGY CONSUMPTION OF A MANUFACTURING LINE WITHIN THE VIRTUAL FACTORY FRAMEWORK](https://www.researchgate.net/publication/313420138_INTEGRATING_DISCRETE_EVENT_SIMULATION_WITH_ENERGY_CONSUMPTION_OF_A_MANUFACTURING_LINE_WITHIN_THE_VIRTUAL_FACTORY_FRAMEWORK)
- [Discrete-Event Modeling – AnyLogic Simulation Software](https://www.anylogic.com/use-of-simulation/discrete-event-simulation/)
- [Open-source discrete-event simulation software for applications in production and logistics: An alternative to commercial tools? - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1877050921004038)
- [GitHub - fschuetz04/simgo: Discrete-event simulation in Go using goroutines · GitHub](https://github.com/fschuetz04/simgo)
- [pypi.org](https://pypi.org/project/simulatte/)
- [pypi.org](https://pypi.org/project/factorysimpy/0.1.0b1/)
- [GitHub - bgmerrell/simgo: A discrete-event simulation framework in Go / golang (and based on simpy) · GitHub](https://github.com/bgmerrell/simgo)
- [GitHub - agoussia/godes: Godes-Library to Build Discrete Event Simulation Models in Go (http://golang.org/) · GitHub](https://github.com/agoussia/godes)

## User:

> 9/11/2026 13:50:20

Rate the languages for these kinds of complex simulation and connections for various types of machines simulating an entire factory not just one machine and each will have lots of sensors. Rate it out of 10 with the tools and ease of development fit for the rest of the project and then the speed of execution too and rank the best one I should use. Research various languages

## Assistant:

> 9/11/2026 13:50:45

> Ranking programming languages across several key criteria.
>
> - Comparing languages for a large-scale factory simulation project.
> - Julia discrete event simulation ConcurrentSim manufacturing performance
> - Ranking programming languages across several key criteria.
> - **Done**

Here's the full comparison across languages actually viable for a multi-machine, multi-sensor factory DES, rated on three axes: **DES/simulation ecosystem maturity**, **ease of fit with the rest of your pipeline** (GNN, causal discovery, LLM narration — all Python), and **raw execution speed**.

| Language | Ecosystem/Tooling | Dev Ease + Pipeline Fit | Execution Speed | Notes |
|---|---|---|---|---|
| **Python (SimPy/FactorySimPy)** | 8/10 | 10/10 | 4/10 | FactorySimPy is purpose-built for manufacturing — model plants as graphs, nodes = machines, edges = conveyors/transport, ships both accelerated and real-time modes for digital twins. Same language as your entire ML/causal/LLM stack — zero integration friction. |
| **Go (godes/simgo)** | 6/10 | 7/10 | 8/10 | `godes` is mature (MIT, maintained since 2013), models each machine as a goroutine — genuinely natural fit for "many machines running concurrently." Fast, but you'll be crossing a language boundary (gRPC/JSON/files) to feed the Python ML layers. |
| **Julia (ConcurrentSim.jl)** | 6/10 | 6/10 | 8/10 | Directly SimPy-inspired (same API concepts, easy migration path), one of the longest-lived Julia packages. Julia's JIT gives near-C speed, and Julia interops with Python reasonably well via PyCall/PythonCall — a genuinely underrated middle ground. Smaller community than Python or Go though. |
| **Rust (sim/desru/RustSim)** | 3/10 | 4/10 | 10/10 | Fastest possible, but the DES crates are small, low-adoption, hobby-scale — you'd be building your own simulation engine, not using a mature one. High implementation tax for a semester timeline. |
| **C++ (custom/roll-your-own)** | 4/10 | 3/10 | 10/10 | Top-tier raw speed, but no manufacturing-specific DES library worth adopting off the shelf — you're writing an event loop, scheduler, and resource model from scratch. Worst ease-of-integration with your Python ML stack (pybind11 needed, more friction than Go/Julia). |

**Ranking for your actual project (weighted toward pipeline fit, since simulation speed isn't your bottleneck at this scale):**

1. **Python / FactorySimPy — winner.** You already know Python, your GNN/causal-discovery/LLM layers are all Python, and FactorySimPy specifically gives you the graph-structured plant model your causal layer needs, natively, in the same process. A few dozen sensors across a multi-machine line is nowhere near enough load to make SimPy's speed a real constraint — you'll hit ML-layer bottlenecks (GNN training, causal discovery) long before the simulator is the slow part.
2. **Go (godes)** — the right second choice *only if* profiling later shows the simulator itself is genuinely too slow (e.g., you're doing thousands of parallel counterfactual replays for root-cause validation, as discussed earlier). Cheap to learn, goroutines map naturally to "many machines," and you'd call it as a subprocess/service from Python rather than trying to unify languages.
3. **Julia** — a legitimate dark horse if you want speed *and* to stay closer to a Python-like syntax/workflow, but it adds a third language to a project that already has enough moving parts, for a benefit you probably won't need.
4. **Rust** — skip for the core simulator. Save it, if at all, for one narrow proven hot-path later (exposed via PyO3), not as your foundation — the ecosystem just isn't there yet for manufacturing DES.
5. **C++** — skip entirely. Best speed on paper, worst cost/benefit for your actual constraints (semester timeline, small-scale sim, heavy Python ML pipeline).

**Bottom line:** build the twin in Python/FactorySimPy. Don't reach for a second systems language until you've actually measured a bottleneck — right now it would be optimizing a part of the system that isn't slow, at the cost of the part that's genuinely hard (the causal tracing and explanation layer).

---

**Sources:**

- [GitHub - JuliaDynamics/ConcurrentSim.jl: A discrete event process oriented simulation framework written in Julia. Formerly named SimJulia! · GitHub](https://github.com/JuliaDynamics/ConcurrentSim.jl)
- [ConcurrentSim.jl/docs/src/index.md at master · JuliaDynamics/ConcurrentSim.jl](https://github.com/JuliaDynamics/ConcurrentSim.jl/blob/master/docs/src/index.md)
- [ConcurrentSim.jl/docs/src/guides/basics.md at master · JuliaDynamics/ConcurrentSim.jl](https://github.com/JuliaDynamics/ConcurrentSim.jl/blob/master/docs/src/guides/basics.md)
- [Home · ConcurrentSim](https://juliadynamics.github.io/ConcurrentSim.jl/dev/)
- [ConcurrentSim.jl/docs/src/tutorial.md at master · JuliaDynamics/ConcurrentSim.jl](https://github.com/JuliaDynamics/ConcurrentSim.jl/blob/master/docs/src/tutorial.md)
- [Discrete event simulation framework for discrete time - Performance - Julia Programming Language](https://discourse.julialang.org/t/discrete-event-simulation-framework-for-discrete-time/55436)
- [Simulate v0.2.0, a Julia package for discrete event simulation - Package Announcements - Julia Programming Language](https://discourse.julialang.org/t/simulate-v0-2-0-a-julia-package-for-discrete-event-simulation/31822)
- [Home · SimJulia](https://juliadynamics.github.io/ConcurrentSim.jl/v0.5/)
- [Discrete event simulation with constraint based scheduling analysis](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8000946)
- [Digital Twins and Their Applications in Modeling Different Levels of Manufacturing Systems: A Review](https://arxiv.org/pdf/2511.06119)

## User:

> 9/11/2026 13:53:16

What anamoly detection models can I use for this and what about training data and testing and are there pre made models and also what models should I use

## Assistant:

> 9/11/2026 13:53:48

> Exploring anomaly detection models for industrial sensor data.
>
> - Exploring anomaly detection models for industrial sensor data.
> - best multivariate time series anomaly detection models 2026 GDN USAD Anomaly Transformer pretrained
> - **Done**

Now let me check for pretrained models / off-the-shelf toolkits, and the reference implementations with code (GDN, TranAD, USAD repos) plus Merlion/PyOD-type libraries.

> Recommending models suited to the reconstruction project.
>
> - Merlion PyOD TSAD library github pretrained anomaly detection benchmark toolkit
> - Recommending models suited to the reconstruction project.
> - **Done**

**Model categories, and what actually fits your project:**

**1. Classical/statistical baselines (build these first — they're your sanity check, not your final model)**
Isolation Forest, LOF, one-class SVM — all in **PyOD**, a mature library (46M+ downloads, 60+ detectors) with a consistent `fit/predict/decision_function` API. Use these to get a working end-to-end pipeline fast and to know what "trivial" detection looks like before you reach for anything fancy.

**2. Deep reconstruction/forecasting models (the standard modern baseline tier)**
- **USAD** — dual autoencoders with adversarial training, strong especially on SWaT.
- **OmniAnomaly** — stochastic recurrent net, good at capturing temporal dependence, though it can miss anomalies that stay close to normal trends.
- **TranAD** — transformer-based, captures long-range dependencies, but doesn't explicitly model sensor-to-sensor spatial structure.
- **Anomaly Transformer** — uses "association discrepancy" (how differently a point attends to its neighbors vs. the whole series) as the anomaly signal — a genuinely different and well-regarded idea from 2021 that's still a common baseline.

**3. Graph-based models — this is your best fit, given your topology-prior design**
- **GDN (Graph Deviation Network)** — learns a sensor dependency graph and attention-based deviations, strong performance specifically on **MSL** and comparable ICS-style datasets. Since you're already planning to seed a known plant topology, GDN is the most natural architecture to adapt — instead of learning the graph from scratch, you fix the skeleton from your plant design and let GDN learn edge weights/attention on top of it.
- **MTAD-GAT** — graph attention + GRU, explicitly models both feature-feature and time-time correlations, and research shows adding GRU/Informer on top of the GAT structure improves results specifically on WADI-style data.
No single model wins everywhere — comparisons consistently show GDN strongest on MSL, USAD strong on SWaT, other transformer variants stronger on WADI/SMD. That's actually useful: run 2-3 models on your data and let the comparison itself be a result you report, not a weakness.

**Are there pretrained models you can just download and use? Honestly — no, not usefully.** This is the important caveat: unlike vision or language models, industrial anomaly detectors are trained on the specific sensor topology, ranges, and normal-operation dynamics of one plant. A model pretrained on SWaT's water-treatment sensors doesn't transfer to your factory's vibration/temperature sensors — the feature space itself is different. What you *can* reuse is **architecture and code**, not weights: GDN, USAD, TranAD, MTAD-GAT all have public reference implementations you adapt and retrain on your own simulator's data. That retraining is expected, not a gap in your project — it's normal for this domain.

**Training data — three sources, layered:**
1. **Your simulator's normal-operation data** — run it clean for a long simulated period, this is your unsupervised training set (all these models train on normal data and detect deviations at inference).
2. **Fault-injected data from your simulator** — this is where your project is actually stronger than most papers: you know ground truth (which component broke, when, how it propagated), so you get perfectly labeled anomaly data for free, something SWaT/WADI users often lack in this quality.
3. **Public datasets (SWaT, WADI, or SMD/MSL/SMAP) as an external validation sanity check** — train/tune on your own data, but also run your model on a public benchmark to show it's not just overfit to your simulator's quirks. This is a real credibility boost for a semester report.

**Testing/evaluation — two separate things to measure, don't conflate them:**
- **Detection quality**: precision/recall/F1 (point-adjusted, the standard convention in this literature), plus detection latency (how many timesteps after the true anomaly onset did you flag it).
- **Root-cause quality** (your actual differentiator): use the AC@1/AC@3/Avg@5 metric convention from RCAEval — did the true injected root cause appear in your top-1/top-3/top-5 ranked explanation candidates? This is the number that proves your trace works, not just your detector.

**What I'd actually use, concretely:**
- **Prototype/baseline fast**: PyOD's Isolation Forest, just to get the pipeline running end to end in week 1-2.
- **Core detector**: GDN, adapted to use your known plant topology as the graph prior instead of learning it blind — this is the single best-fit model given everything you've described.
- **Comparison baseline**: USAD or TranAD trained on the same data, so your report can say "GDN with topology prior outperforms topology-agnostic baselines by X%" — a genuine, defensible result.
- **Optional library to wrap all of it**: **Merlion** (Salesforce) gives you a unified interface across models, standardized evaluation, and visualization — useful glue so you're not writing training/eval boilerplate for each architecture separately.

---

**Sources:**

- [DDMT: Denoising Diffusion Mask Transformer Models for Multivariate Time Series Anomaly Detection](https://arxiv.org/pdf/2310.08800)
- [Pi-transformer: A prior-informed dual-attention model for multivariate time-series anomaly detection](https://arxiv.org/pdf/2509.19985)
- [Graph Attention Network and Informer for Multivariate Time Series Anomaly Detection - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10935277/)
- [AnomalyBERT: Self-Supervised Transformer for Time Series Anomaly Detection using Data Degradation Scheme](https://arxiv.org/pdf/2305.04468)
- [Pre-training Enhanced Transformer for multivariate time series anomaly detection - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1566253525002441)
- [Multivariate Time Series Anomaly Prediction Based on Forecasting and Reconstruction Using Transformer with Temporal and Feature-Wise Attention | Springer Nature Link](https://link.springer.com/chapter/10.1007/978-3-032-05962-8_6)
- [Efficient anomaly detection in multivariate time series using two- stage attention and transformer architecture - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2590123026013757)
- [GitHub - rob-med/awesome-TS-anomaly-detection: List of tools & datasets for anomaly detection on time-series data. · GitHub](https://github.com/rob-med/awesome-TS-anomaly-detection)
- [GitHub - yzhao062/pyod: A Python library for anomaly detection across tabular, time series, graph, text, image, and audio data. 60+ detectors, benchmark-backed ADEngine orchestration, and an agentic workflow for AI agents. · GitHub](https://github.com/yzhao062/pyod)
- [GitHub - salesforce/Merlion: Merlion: A Machine Learning Framework for Time Series Intelligence · GitHub](https://github.com/salesforce/Merlion)
- [Merlion/README.md at main · salesforce/Merlion](https://github.com/salesforce/Merlion/blob/main/README.md)
- [github.com](https://github.com/Pekis-crypto/Merlion)
- [GitHub - yzhao062/anomaly-detection-resources: Anomaly detection related books, papers, videos, and toolboxes. Last update late 2025 for LLM and VLM works! · GitHub](https://github.com/yzhao062/anomaly-detection-resources)
- [Block or Report](https://github.com/noppolanak)
- [PyOD (Python Outlier Detection)](https://docsearch.algolia.com/mcp/docs/repo/yzhao062/pyod)

Powered by Claude Exporter (https://www.ai-chat-exporter.net)
