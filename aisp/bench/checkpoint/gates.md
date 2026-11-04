# 阶段门

## public.viba

```bash public
import aisp.bench.checkpoint.gates.types as gates

Gate = gates.Gate
```

## types.viba

```bash types
Gate =
  Oneof
  | "G0" * { 能跑：目标代码在不旁路的情况下能跑完一次前向或一次预填充；产出可运行的最小配置 }
  | "G1" * { 旁路可跑：旁路实现后能跑完同样流程，且 IO 路径未被替换；产出保真边界表 }
  | "G2" * { 小规模对齐：选定度量项在容差内；产出对齐报告的回链 }
  | "G3" * { 逐级 scaling：每一级的不变量都在容差内，偏差有归因；产出 scaling 报告的回链 }
  | "G4" * { 结论登记：回链三要素齐全，覆盖率矩阵更新；产出 recipe.yaml 的 latest_run }
```

## apis.viba
