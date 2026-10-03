from agents.dna import AgentDNA
from core.engine import Engine


class Agent:
    """An agent is fully defined by its DNA (+ the engine seed it runs under)."""

    def __init__(self, dna: AgentDNA):
        self.dna = dna

    def configure_engine(self, engine: Engine) -> None:
        """Apply this agent's DNA to the engine's behaviour.

        Writes to ``engine.config.basal_ganglia``, which the brain reads every
        tick, so genes actually change how the agent acts. Unknown params are
        ignored, so DNA can carry forward-compatible fields.
        """
        params = self.dna.params
        bg = engine.config.basal_ganglia

        if "exploration_bias" in params:
            explore = float(params["exploration_bias"])
            bg.forward_bias = 0.6 + 0.6 * explore  # 0.6 .. 1.2
            bg.novelty_gain = 0.1 + 0.4 * explore  # 0.1 .. 0.5
        if "pain_avoidance" in params:
            avoid = float(params["pain_avoidance"])
            bg.pain_avoidance = 0.2 + 0.8 * avoid  # 0.2 .. 1.0
            bg.rest_pain_gain = 0.4 + 0.8 * avoid  # 0.4 .. 1.2
        if "turn_bias" in params:
            bg.turn_bias = float(params["turn_bias"])
