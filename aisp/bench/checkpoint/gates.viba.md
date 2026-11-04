# 阶段门

## types.viba

```bash types
Gate =
  Oneof
  | "G0" * { 能跑：目标代码在不旁路的情况下能跑完一次前向或一次预填充；产出可运行的最小配置 }
  | "G1" * { 旁路可跑：旁路实现后能跑完同样流程，且 IO 路径未被替换；产出保真边界表 }
  | "G2" * { 小规模对齐：选定度量项在容差内；产出对齐报告的回链 }
  | "G3" * { 逐级 scaling：每一级的不变量都在容差内，偏差有归因；产出 scaling 报告的回链 }
  | "G4" * { 结论登记：回链三要素齐全，覆盖率矩阵更新；产出 recipe.yaml 的 latest_run }

GateVerdict =
  Object
  * $gate (Gate * { 判的是哪道门 })
  * $passed (bool * { 这道门是否通过 })
  * $evidence (str * { 这道门的产出放在哪；产出不齐全就不算通过 })
```

## 基本操作

1. 判门：拿到这道门的产出，对照这道门的要求，答通过或不通过。
2. 按顺序判：G0 到 G4 一道一道过，前一道不通过就不判后一道。

## apis.viba

```bash apis
import aisp.bench.checkpoint.gates.types as gates

Pass =
     gates.GateVerdict
  <- $gate (gates.Gate * { 要判的那道门 })
  <- $evidence (str * { 这道门的产出放在哪；没有产出就没有可判的东西 })
  <- {
    判一道门：产出齐全且达到这道门的要求才算通过；G0 到 G4 按顺序来，前一道没过就不判后一道
  }
```
