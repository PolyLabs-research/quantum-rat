# Quantum Rat v2 — Engineering Specification

> Auto-exported from `Quantum_Rat_v2.0_Engineering_Specification.docx` for diffable
> review. The `.docx` remains the formatting source; regenerate this file if the
> `.docx` changes. Tables and lists are flattened; see the `.docx` for exact layout.

---

# QUANTUM RAT v2.0

Engineering Specification

Simulation as Instrument

Version 2.1.0

December 2025

Status: Draft for Review

| v2.0 Updates from Lead Dev Feedback: - Added Egomotion/Proprioception to Observation contract - Defined canonical TickData schema for metrics logging - Added Tournament/Agent architecture for multi-agent competition |
| --- |

## Document Control

| Document ID | QR-ENG-SPEC-002 |
| --- | --- |
| Version | 2.1.0 |
| Supersedes | QR-ENG-SPEC-001 (v1.0) |
| Target | Simulation as Instrument |

## 1. Executive Summary

This specification defines the complete refactoring of the Quantum Rat simulation platform. The primary technical change replaces speculative "quantum microtubule" dynamics with an established Criticality-Based Neural Model, while restructuring the codebase to support rigorous scientific inquiry, deterministic replay, and multi-agent tournaments.

### 1.1 Core Principles

- Strict Boundaries: The Brain never accesses the World directly. It receives an immutable Observation and returns an Action.

- Config-Driven: All magic numbers must exist in a validated SimConfig object.

- Determinism First: A single random seed controls the entire simulation tree. Regressions are caught via checksum comparison.

- Criticality as Core: The central dynamic is a CriticalityField (branching process) replacing quantum abstractions.

- Metrics First: Logging is not an afterthought. A canonical TickData schema is enforced from Day 1.

## 2. Directory Structure

The directory structure enforces separation of concerns. NEW items from v2.0 are highlighted.

quantum_rat/

├── app/ # View Layer (Flask)

│ ├── server.py # App factory

│ └── routes/ # Endpoints (read-only access to Engine)

├── core/ # The "God" Layer (Physics & Truth)

│ ├── engine.py # Main loop & state management

│ ├── world.py # Geometry, Collision, Targets

│ ├── entities.py # RatBody, Predator (physics)

│ ├── rng.py # Seeding authority

│ └── pipeline.py # Tick execution order

├── brain/ # The Agent Layer

│ ├── agent.py # NEW: Container (Brain + DNA)

│ ├── memory/ # State persistence (BrainState)

│ ├── contracts.py # IO Contracts (Observation, Action)

│ ├── orchestrator.py # Component wiring

│ └── systems/ # Neural subsystems

│ ├── criticality.py # CriticalityField

│ ├── spatial.py # Grid/Place/HD cells

│ ├── neuromod.py # DA/5HT/NE/ACh systems

│ ├── trn.py # Thalamic gating

│ ├── basal_ganglia.py # Action selection

│ └── metabolism.py # Astrocyte/ATP model

├── experiments/ # Controller Layer

│ ├── runner.py # Headless experiment runner

│ ├── tournament.py # NEW: Multi-agent competition

│ └── protocols/ # Lab assays (T-Maze, Open Field)

├── metrics/ # Data Science Layer

│ ├── logger.py # Structured CSV/JSON logger

│ ├── schema.py # NEW: TickData dataclass

│ └── analysis.py # Avalanche analysis tools

└── tests/ # Validation Suite

├── fixtures/ # Baseline traces

└── unit/ # Component tests

## 3. Data Contracts (The Spine)

These data structures define the API between systems. They must be implemented as Python dataclasses (frozen where appropriate) to ensure type safety.

### 3.1 Simulation Configuration

core/config.py

@dataclass

class CriticalityConfig:

enabled: bool = True

field_size: int = 32

fire_threshold: float = 0.6

coupling: float = 0.25

noise_drive: float = 0.02

refractory_reset: bool = True # True: reset to 0

kappa_ema_alpha: float = 0.05 # Smoothing factor

### 3.2 The IO Boundary

brain/contracts.py

Input to Brain:

@dataclass(frozen=True)

class Observation:

"""Immutable snapshot provided to the Brain."""

vision_rays: Tuple[VisionRay, ...] # [dist, type, angle]

whisker_hits: Tuple[bool, bool] # Left/Right contact

pain_signal: float # 0.0 - 1.0

energy_levels: Dict[str, float] # {'atp', 'glycogen'}

# NEW v2.0: Proprioception for path integration

# Brain needs this for grid cells since it cannot

# know absolute coordinates.

egomotion: Tuple[float, float] # [forward_delta, turn_delta]

Output from Brain:

@dataclass(frozen=True)

class Action:

"""The only way the Brain affects the World."""

velocity_vector: Tuple[float, float] # Continuous movement

focus_direction: float # Head angle

eat_trigger: bool # Attempt to consume

turn_rate: float = 0.0 # Scalar fallback

speed: float = 0.0 # Scalar fallback

### 3.3 The Brain State

brain/memory/state.py

@dataclass

class BrainState:

# Neuromodulators (0..1 normalized)

dopamine: float = 0.5

serotonin: float = 0.5

norepinephrine: float = 0.2

acetylcholine: float = 0.2

# Core Dynamics

kappa: float = 1.0 # Branching ratio (smoothed)

entropy: float = 0.0 # Shannon entropy of field

arousal: float = 0.0 # Global gain factor

# Cognitive

working_memory: np.ndarray # default: zeros(16)

spatial_belief: np.ndarray # default: zeros(2)

in_microsleep: bool = False

### 3.4 The Canonical Log Record

NEW in v2.0 - This schema is the single source of truth for analysis and UI.

metrics/schema.py

@dataclass

class TickData:

"""Single source of truth for analysis and UI."""

tick: int

agent_id: int

pos: Tuple[float, float]

score: int

# Brain vitals

kappa: float

avalanche_size: int

neuromodulators: Dict[str, float]

# Assay info

protocol_name: str

trial_number: int

### 3.5 The Agent Container

NEW in v2.0 - Wraps Brain + DNA for tournament/genetic algorithm support.

brain/agent.py

@dataclass

class AgentDNA:

"""Heritable parameters for genetic algorithms."""

fear_weight: float = 1.0

curiosity_weight: float = 1.0

hunger_weight: float = 1.0

base_metabolism: float = 1.0

ei_balance: float = 1.0 # Criticality setpoint

class Agent:

"""Container binding Brain instance to DNA."""

id: int

dna: AgentDNA

brain: Brain

fitness: float = 0.0

generation: int = 0

## 4. The Criticality Field (Core Mechanic)

Replacing the microtubule wavefunction is a Branching Process on a Lattice.

### 4.1 Specification

- Structure: A 2D grid (N x M) of activation potentials A[i,j]

- Firing Rule: Cell fires if A[i,j] > fire_threshold

- Propagation: Fired cells distribute energy: A_neighbor += A[i,j] * (E/I) * coupling / n_neighbors

- Reset: Fired cells reset to 0 (refractory)

- Drive: Add small noise each tick: A += noise_drive * N(0,1)

### 4.2 Control Parameter (E/I Ratio)

- Base: Configurable baseline from AgentDNA.ei_balance (default 1.0)

- Norepinephrine: Increases gain (risk of supercriticality/panic)

- Acetylcholine: Boosts effective excitation (encoding mode)

- ATP: Low energy clamps dynamics to subcritical (anesthesia-like)

### 4.3 Metrics Calculation

Branching Ratio (kappa):

- Raw: kappa_raw = N_firing(t+1) / max(1, N_firing(t))

- Stored: EMA smoothed value using kappa_ema_alpha

Avalanche:

- Definition: A contiguous run where N_firing(t) > 0

- Event logged to TickData if total_size > threshold

## 5. The Execution Pipeline

The simulation loop (core/engine.py) enforces a rigid order of operations.

TICK_ORDER = [

"world_physics", # 1. Predator, collisions, movement

"sensors", # 2. Raycast -> Observation (incl. Egomotion)

"physiology", # 3. Astrocyte decay (ATP consumption)

"neuromodulation", # 4. Update DA/5HT based on pain/reward

"criticality", # 5. Run avalanche -> Output kappa

"trn_gating", # 6. Gating using kappa + arousal

"spatial", # 7. Grid/Place/HD cells using Egomotion

"action_selection", # 8. Basal Ganglia votes -> Action

"motor_execution", # 9. Apply Action to Rat Body

"logging" # 10. Write TickData to history

]

Note: Steps 2 and 7 now use egomotion for proprioceptive path integration. Step 10 writes the canonical TickData record.

## 6. Tournament System

NEW in v2.0 - Preserves genetic algorithm and multi-agent competition logic.

### 6.1 TournamentManager

experiments/tournament.py

class TournamentManager:

"""Orchestrates multi-agent competition."""

def __init__(self, population_size: int, config: SimConfig):

self.agents: List[Agent] = []

self.generation: int = 0

self.history: List[TickData] = []

def run_generation(self, ticks: int) -> List[float]:

"""Run all agents, return fitness scores."""

def select_and_breed(self) -> None:

"""Tournament selection + crossover + mutation."""

def get_leaderboard(self) -> List[Tuple[int, float]]:

"""Return sorted (agent_id, fitness) pairs."""

### 6.2 Fitness Function

Default fitness calculation:

fitness = (targets_collected * 10)

+ (survival_ticks * 0.1)

- (predator_hits * 50)

+ (exploration_bonus)

## 7. Implementation Strategy

### Phase 1: The Skeleton (Days 1-2)

Goal: Running Flask app returning dummy data but respecting new architecture.

- Create directory tree

- Implement rng.py, config.py, and all data contracts

- Implement Engine scaffold

- Port app/server.py to use new SimulationState

- Constraint: Ensure /determinism_check endpoint works

### Phase 2: The Physical World (Days 3-4)

Goal: Rat moves, collides, and starves.

- Port world.py (Grid logic)

- Implement sensors.py (Raycasting + Egomotion generation)

- Implement astrocyte.py (Metabolism)

- Verification: Rat sits still and slowly dies of energy depletion

### Phase 3: The Critical Brain (Days 5-7)

Goal: Intrinsic dynamics with measurable kappa.

- Implement CriticalityField

- Implement NeuromodulatorSystem

- Wire ATP -> Subcriticality

- Verification: Frontend heatmap active; logs show kappa metrics

### Phase 4: Intelligence & Competition (Days 8-10)

Goal: Goal-directed behavior and Tournament support.

- Port BasalGanglia, Spatial (using Egomotion), TRN

- Implement Agent and AgentDNA classes

- Implement TournamentManager

- Verification: "Start Tournament" button runs multiple agents with different DNA

## 8. Testing & Validation

### 8.1 Regression Baseline

Before deleting old code:

- Run current app.py (v0.9)

- Record trace [Position, Score, Frustration] for 2000 frames

- Save to tests/fixtures/legacy_baseline.json

The new engine will run against this to quantify behavioral drift.

### 8.2 Criticality Validation

experiments/criticality_validation.py

- Sweep E/I ratio around 1.0

- Log kappa distribution and avalanche sizes

Pass Criteria:

- Subcritical (kappa < 1): Small avalanches

- Critical (kappa ~ 1): Power-law size distribution

- Supercritical (kappa > 1): Runaway cascades

### 8.3 Egomotion Validation

NEW in v2.0

- Run agent in open field for 1000 ticks

- Sum egomotion deltas to reconstruct path

- Compare reconstructed path to actual positions from TickData

- Pass Criteria: Drift < 5% of total distance traveled

## 9. Acceptance Criteria

### 9.1 Functional Requirements

- All /api endpoints return responses matching v0.9 JSON schema

- Deterministic mode produces identical output for identical inputs

- Frontend visualization works without modification

- TickData schema enforced for all logged metrics

- Tournament button spawns multiple agents with distinct DNA

### 9.2 Scientific Requirements

- Avalanche size distribution exhibits power-law scaling at kappa ~ 1

- Branching ratio responds appropriately to NE and ATP modulation

- Grid cell path integration uses egomotion (no position cheating)

- Behavioral metrics within 10% of v0.9 baseline

### 9.3 Code Quality Requirements

- No file exceeds 500 lines

- All public functions have docstrings

- Type hints on all function signatures

- Unit test coverage >= 80% for brain/systems/

--- End of Specification v2.0 ---
