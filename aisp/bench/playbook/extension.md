# 扩展：从缺口到新版本

## 背景

评估集是静态产物：一个版本的用例清单构建完成之后，不会自己变化。新模型出现、框架升级、并行策略变化时，覆盖度会随时间下降；本篇要解决的是让 playbook 持续产出覆盖不衰减的新版本，并且不让历史结论悄悄失效。对外常说的「自进化」指的是 playbook 的这套能力，不是评估集自己会动。

## 问题

```viba extension
import configs

ExtensionAxis =
  Oneof
  | "arch_family" * Hint[{ 模型结构轴：按 [model-code-collection.md](model-code-collection.md) 的架构族划分 }]
  | "model_scale" * Hint[{ 参数量分桶，至少 6 个量级 }]
  | "attention" * Hint[{ MHA / GQA / MQA / MLA / 线性注意力 / 滑动窗口 }]
  | "framework" * Hint[{ vllm / sglang / deepinfer }]
  | "parallel" * Hint[{ DP / TP / PP / EP 的代表组合 }]
  | "cluster" * Hint[{ S0–S5；档位定义见 [scaling.md](scaling.md) 的 levels 模块 }]
  | "io_feature" * Hint[{ 小请求密集 / 大块顺序 / 高并发 / 热点访问 / 突发 }]
  | "storage_backend" * Hint[{ GPFS / HDFS / Alluxio / Ceph / JuiceFS }]
  | "storage_adapter" * Hint[{ mooncake / torchstore / bytecheckpoint }]

ExtensionCoverage =
  Object
  * $axes (list[ExtensionAxis] * Hint[{ 矩阵的轴；由各配方的 metrics.yaml 定义，但必须包含「模型结构」与「系统规模」两个轴 }])
  * $cells (list[ExtensionCell] * Hint[{ 矩阵的每个格子；每个格子记录用例数、最近一次通过时间、最近一次失败 }])

ExtensionCell =
  Object
  * $axes (dict[str, str] * Hint[{ 这个格子的位置：轴名到取值，轴名取自 ExtensionAxis }])
  * $cases (int * Hint[{ 这个格子里的用例数 }])
  * $last_passed_at ((str | nil) * Hint[{ 最近一次通过时间；从未通过给 nil }])
  * $last_failed_at ((str | nil) * Hint[{ 最近一次失败时间；从未失败给 nil }])
  * $empty ((ExtensionEmptyKind | nil) * Hint[{ 空格子属于哪一种；格子里有用例时给 nil }])

ExtensionEmptyKind =
  Oneof
  | "should_exist" * Hint[{ 应该有但没有：登记为缺口，进候选生成 }]
  | $not_needed (ExtensionExemption * Hint[{ 明确不需要：登记为豁免，写理由与复核日期；豁免必须定期复核，否则会变成永久空白 }])

ExtensionExemption =
  Object
  * $reason (str * Hint[{ 豁免理由：写清为什么这个格子明确不需要覆盖 }])
  * $review_date (str * Hint[{ 复核日期：豁免必须定期复核，否则会变成永久空白 }])

ExtensionGap =
  Object
  * $cell (ExtensionCell * Hint[{ 缺口所在的格子；这个格子的 empty 为 should_exist }])
  * $priority (float * Hint[{ 优先级 = 覆盖权重 × 结构新颖度 × 规模重要性 / 预计成本；覆盖权重取该格子在下游使用中被引用的次数，结构新颖度取与现有样本的最小结构距离、越大越新，规模重要性取目标规模与该格子规模的差距，预计成本由配方声明的单次运行成本估算。分数只用于排序，不用于自动决定入集，入集决策留给人 }])

ExtensionCandidateSource =
  Oneof
  | "model_list_new_item" * Hint[{ 模型清单的新增项：按结构距离挑选，避免与现有样本重复 }]
  | "architecture_family_gap" * Hint[{ 架构族缺口：从公开模型里找该族的最新与最大样本 }]
  | "framework_capability_gap" * Hint[{ 框架能力缺口：框架新版本引入的缓存/传输能力，构造对应用例 }]
  | "failure_reproduction" * Hint[{ 失败复现：从失败分类里取代表性样本，构造成最小复现用例 }]
  | "load_gap" * Hint[{ 负载缺口：用现有模型搭配未覆盖的负载模式 }]

ExtensionCandidate =
  Object
  * $source (ExtensionCandidateSource * Hint[{ 这个候选来自哪条生成路径 }])
  * $model (configs.Model * Hint[{ 候选用例的模型：模型清单里的标识与代码 commit }])
  * $config (str * Hint[{ 候选用例的配置 }])
  * $load (str * Hint[{ 候选用例的负载 }])
  * Hint[{ 候选用例必须带完整运行规格，能直接提交给评估服务；生成出来但不能跑的候选，不算候选 }]

ExtensionRegressionScope =
  Oneof
  | "smoke" * Hint[{ 冒烟：每个配方的 S0 最小用例，每次提交 }]
  | "regular" * Hint[{ 常规：全部 S0 + 抽样 S1，每日 }]
  | "full" * Hint[{ 全量：全部用例，每周或发布前 }]

ExtensionRegressionVerdict =
  Oneof
  | "passed" * Hint[{ 通过：度量在容差内；更新基线与覆盖矩阵的最近一次通过时间 }]
  | "not_comparable" * Hint[{ 不可比：度量超出容差，但运行规格有变化；需要重跑同规格 }]
  | "failed" * Hint[{ 不通过：度量超出容差，规格相同；进入排查，冻结相关结论，生成排查任务，不自动改配方 }]
  | "no_conclusion" * Hint[{ 无结论：运行失败；不计入通过率，保留原基线不覆盖；连续三次无结论的用例标记为不稳定，退出回归集并进入修复队列 }]

ExtensionRegression =
  Object
  * $candidate (ExtensionCandidate * Hint[{ 这次回归针对哪个候选用例 }])
  * $scope (ExtensionRegressionScope * Hint[{ 这次回归跑多大范围 }])
  * $baseline (str * Hint[{ 基线：上次通过版本的结果，不是上一次的结果 }])
  * $verdict (ExtensionRegressionVerdict * Hint[{ 这次回归的判定结论 }])

ExtensionVersion =
  Object
  * $recipe (str * Hint[{ 配方版本；流程、旁路方式、验收标准变化时递增 }])
  * $cases (str * Hint[{ 用例集版本；增删用例、调整负载配置时递增 }])
  * $metrics (str * Hint[{ 指标版本；度量定义变化时递增 }])
  * Hint[{ 整个评估集版本写成 <配方版本>+<用例集版本>.<指标版本>；服务在运行时校验三者兼容，评估集版本变更必须写进 CHANGELOG.md，并注明影响的历史结论范围 }]

ExtensionTrigger =
  Oneof
  | "new_model_release" * Hint[{ 新模型发布。信号来源：模型清单定期扫描、发布公告；响应：加入候选池，跑可跑性验证，按覆盖度决定是否入集 }]
  | "framework_release" * Hint[{ 框架新版本。信号来源：框架发布源、镜像更新；响应：适配层回归，失败则标记适配过期 }]
  | "coverage_decline" * Hint[{ 覆盖度下降。信号来源：覆盖度矩阵的空白格子增多；响应：生成针对空白格子的候选 }]
  | "failure_mode_change" * Hint[{ 失败模式变化。信号来源：评估服务里新增的失败分类；响应：新增用例复现该失败 }]
  | "new_parallel_strategy" * Hint[{ 新并行策略。信号来源：训练或推理配置变更；响应：新增并行组合的用例 }]
  | "storage_backend_change" * Hint[{ 存储后端变更。信号来源：基础设施变更通知；响应：重跑受影响后端的对齐用例 }]
  | "overturned_conclusion" * Hint[{ 历史结论被推翻。信号来源：回归时与基线不一致；响应：冻结相关结论，进入人工排查 }]
```

## 基本操作

闭环有四个操作：发现缺口、生成候选、回归验证、版本收敛。发现缺口扫描覆盖度矩阵的空白格子，结合失败模式与外部信号，把「应该有但没有」的格子登记为带优先级的缺口。生成候选结合缺口清单、模型清单与框架发布信息，按候选来源产出模型、配置、负载齐全的候选用例，自动生成后交人确认入集。回归验证按冒烟、常规或全量范围跑候选用例，与上次通过版本的基线比较，得到通过、不可比、不通过或无结论。版本收敛把回归结论收进新的评估集版本，更新回链并写变更记录，然后回到发现缺口。这四个操作由触发条件启动，触发信号要写进服务配置，不允许靠人记得去跑。

## 接口

```viba extension_api
import configs
import extension

FindGap =
     list[extension.ExtensionGap]
  <- $coverage (extension.ExtensionCoverage * Hint[{ 覆盖度矩阵：轴与格子；缺口从空白格子里来 }])
  <- $failures (list[str] * Hint[{ 失败模式：评估服务里已有的失败分类 }])
  <- $signals (list[str] * Hint[{ 外部信号：模型清单、框架发布与基础设施变更 }])
  <- Hint[{ 发现缺口：扫描覆盖度矩阵的空白格子，结合失败模式与外部信号，把应该有但没有的格子登记为缺口，按覆盖权重 × 结构新颖度 × 规模重要性 / 预计成本排序；返回带优先级的缺口清单。分数只用于排序，不用于自动决定入集 }]

ProposeCandidate =
     list[extension.ExtensionCandidate]
  <- $gaps (list[extension.ExtensionGap] * Hint[{ 上一步产出的缺口清单 }])
  <- $models (list[configs.Model] * Hint[{ 模型清单里的模型；新增项按结构距离挑选，避免与现有样本重复 }])
  <- $frameworks (list[str] * Hint[{ 框架发布信息；框架新版本引入的缓存/传输能力用来构造对应用例 }])
  <- Hint[{ 生成候选：按缺口与候选来源返回模型、配置、负载齐全的候选用例；生成出来但不能跑的候选不算候选。自动生成，入集需要人工确认 }]

Regress =
     list[extension.ExtensionRegression]
  <- $candidates (list[extension.ExtensionCandidate] * Hint[{ 上一步产出的候选用例 }])
  <- $baseline (str * Hint[{ 现有基线：上次通过版本的结果，不是上一次的结果 }])
  <- $scope (extension.ExtensionRegressionScope * Hint[{ 这次回归跑多大范围：冒烟、常规或全量 }])
  <- Hint[{ 回归验证：按范围跑候选用例，与基线比较；返回每个候选的通过、不可比、不通过或无结论。通过更新基线与覆盖矩阵的最近一次通过时间，不通过冻结相关结论并生成排查任务，无结论保留原基线不覆盖 }]

Converge =
     extension.ExtensionVersion
  <- $regressions (list[extension.ExtensionRegression] * Hint[{ 上一步产出的回归结论 }])
  <- Hint[{ 版本收敛：把回归结论收进新版本，按配方版本、用例集版本、指标版本三部分递增；返回新评估集版本，更新回链，并把变更写进 CHANGELOG.md，注明影响的历史结论范围。人工确认 }]
```

## 组织

```viba extension_flow
import extension

ExtensionLoop =
  Object
  * $trigger (extension.ExtensionTrigger * Hint[{ 这次循环由哪条触发条件启动；触发信号要写进服务配置，不允许靠人记得去跑 }])
  * $steps (list[ExtensionStep] * Hint[{ 闭环的四个动作，按发现缺口 → 生成候选 → 回归验证 → 版本收敛 的顺序循环；收敛出的新版本回到第一步继续找缺口 }])

ExtensionStep =
  Oneof
  | $find_gap (list[extension.ExtensionGap] * Hint[{ 第一步，发现缺口：调 extension_api.FindGap；输入是覆盖度矩阵、失败模式与外部信号，产出带优先级的缺口清单 }])
  | $propose_candidate (list[extension.ExtensionCandidate] * Hint[{ 第二步，生成候选：调 extension_api.ProposeCandidate；输入是缺口清单、模型清单与框架发布信息，产出候选用例 }])
  | $regress (list[extension.ExtensionRegression] * Hint[{ 第三步，回归验证：调 extension_api.Regress；输入是候选用例与现有基线，产出通过、不可比、不通过或无结论 }])
  | $converge (extension.ExtensionVersion * Hint[{ 第四步，版本收敛：调 extension_api.Converge；输入是回归结论，产出新评估集版本；新版本回到第一步 }])
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
