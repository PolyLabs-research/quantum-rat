from experiments.protocols.base import Protocol
from experiments.protocols.beacon import BeaconProtocol
from experiments.protocols.foraging import ForagingProtocol
from experiments.protocols.open_field import OpenFieldProtocol
from experiments.protocols.t_maze_toy import TMazeProtocol
from experiments.protocols.morris_water_maze_toy import MorrisWaterMazeProtocol
from experiments.protocols.survival_arena_toy import SurvivalArenaProtocol

__all__ = [
    "Protocol",
    "BeaconProtocol",
    "ForagingProtocol",
    "OpenFieldProtocol",
    "TMazeProtocol",
    "MorrisWaterMazeProtocol",
    "SurvivalArenaProtocol",
]
