"""样本配置基类。

对齐 ``playbook/ckpt-sample-interface.md`` 的 ``configs`` 模块。
样本 repo 里每份配置必须包含这三个子结构；样本可以在此基础上扩展自己的字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args


@dataclass(frozen=True)
class Model:
    id: str         # HuggingFace repo id 之类
    git_commit_id: str


Network = Literal["rdma", "tcp", "none"]
Mount = Literal["local-nvme", "nfs", "fuse"]
ObserveLayer = Literal["app", "sys", "storage"]


@dataclass(frozen=True)
class Topology:
    nodes: int
    gpus_per_node: int
    network: Network
    mount: Mount

    @property
    def total_gpus(self) -> int:
        return self.nodes * self.gpus_per_node


@dataclass(frozen=True)
class ObservationConfig:
    enabled: bool
    sample_rate: float  # 0..1
    layers: tuple[ObserveLayer, ...] = ()


@dataclass(frozen=True)
class SampleConfigBase:
    """样本 repo 每份配置必须含有的基类字段。"""

    model: Model
    topology: Topology
    observe: ObservationConfig


# 供 GetLevel 使用的默认 scaling 阶梯。配方可以在自己的 scaling_plan 里覆盖。
# 边界按总卡数：S0 单机最小，S1 单机多卡或双机，S2 数十至百卡，S3 千卡，S4 万卡，S5 十万卡。
DEFAULT_LEVEL_BOUNDARIES: tuple[tuple[int, str], ...] = (
    (0, "S0"),     # 仅当 nodes == 1 时在此档，见 resolve_level
    (8, "S1"),     # 8..255 卡
    (256, "S2"),   # 256..1023
    (1024, "S3"),  # 1024..9999
    (10000, "S4"), # 10000..99999
    (100000, "S5"),
)


def resolve_level(topology: Topology) -> str:
    """按节点数与每节点卡数落到 S0..S5。阈值由配方阶梯给，这里用默认值。"""

    total = topology.total_gpus
    if topology.nodes == 1:
        return "S0" if topology.gpus_per_node <= 8 else "S1"
    if topology.nodes == 2:
        return "S1"
    for threshold, level in DEFAULT_LEVEL_BOUNDARIES:
        if total < threshold:
            return level
    return "S5"


# 校验用：合法枚举值集合。
NETWORK_VALUES = set(get_args(Network))
MOUNT_VALUES = set(get_args(Mount))
OBSERVE_LAYER_VALUES = set(get_args(ObserveLayer))
