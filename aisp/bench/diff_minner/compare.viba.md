# Diff Minner 比较执行

## 需求背景

提供 `ComparisonGroup` 到 `ComparisonResult` 的执行接口。比较语义、指标口径和三道差距门槛由 `aisp/bench/diff_minner.viba.md` 统一约束，此处不定义第二套判定规则。

## public.viba

```bash public
import aisp.bench.diff_minner.public as diff

CompareGroup = diff.CompareGroup
```

## 基本操作

- 输入是同一份完整 `ComparisonGroup` 和 `GapPolicy`，输出是 `ComparisonResult`。
- EFS 任一轮实测准入失败优先返回 `defect`。仅 GPFS 失败、证据缺失或证据不一致返回 `incomplete`。
- 完整证据至少包含五轮连续配对值、AB/BA 顺序、实际非重叠窗口、逐轮双侧正确性与环境证据。
- 至少一个应用感知指标同时通过统计、实际意义和噪声三道门槛，才返回 `candidate=true` 的 `compared`。
- 存储原生指标只用于归因，不能单独触发候选结论。

## apis.viba

```bash apis
import aisp.bench.diff_minner.public as diff

CompareGroup = diff.CompareGroup
```

参考实现：`aisp/bench/diff_minner/compare/scripts/compare.py`。CLI 是该接口的 JSON 传输绑定：stdin 接收 `$group` 与 `$policy`，stdout 返回 `ComparisonResult`。结构或 JSON 传输错误属于调用错误，不伪造领域结论。

测试：`python3 -m unittest discover -s aisp/bench/diff_minner/compare/tests -v`。测试只使用合成证据，不读取真实存储。
