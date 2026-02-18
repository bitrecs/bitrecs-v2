from typing import Any, NamedTuple, NewType, NotRequired, Protocol, TypeAlias, TypedDict

MinerUID = NewType("MinerUID", int)
BlockNumber = NewType("BlockNumber", int)
EnvironmentId = NewType("EnvironmentId", str)
#TaskUUID = NewType("TaskUUID", str)
#Hotkey = NewType("Hotkey", str)
Seed = NewType("Seed", int)

MinerScores: TypeAlias = dict[MinerUID, dict[EnvironmentId, float]]  # uid -> env_id -> score
MinerThresholds: TypeAlias = dict[MinerUID, dict[EnvironmentId, float]]  # uid -> env_id -> threshold
MinerFirstBlocks: TypeAlias = dict[MinerUID, BlockNumber]  # uid -> block_number