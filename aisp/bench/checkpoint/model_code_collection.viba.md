# 模型代码收集

## 需求背景

样本来自真实模型代码：怎么抓、怎么去重、怎么确认能跑。这三步的结论构成语料，挑样本从这里取，所以本篇发布抓取、去重与可跑性验证三个操作及其类型。

## public.viba

```bash public
import aisp.bench.checkpoint.model_code_collection.types as model_code_collection
import aisp.bench.checkpoint.model_code_collection.apis as model_code_collection_api

CollectionSource = model_code_collection.CollectionSource
CollectionFilter = model_code_collection.CollectionFilter
CollectionManifestEntry = model_code_collection.CollectionManifestEntry
CollectionLicense = model_code_collection.CollectionLicense
CollectionLicenseState = model_code_collection.CollectionLicenseState
CollectionDownload = model_code_collection.CollectionDownload
CollectionCodeFile = model_code_collection.CollectionCodeFile
CollectionFileKind = model_code_collection.CollectionFileKind
CollectionFetchFailure = model_code_collection.CollectionFetchFailure
CollectionCodeRole = model_code_collection.CollectionCodeRole
CollectionCodeRoleEvidence = model_code_collection.CollectionCodeRoleEvidence
CollectionWorkspace = model_code_collection.CollectionWorkspace
CollectionFingerprint = model_code_collection.CollectionFingerprint
CollectionConfigFingerprint = model_code_collection.CollectionConfigFingerprint
CollectionMoeSpec = model_code_collection.CollectionMoeSpec
CollectionPositionalEncoding = model_code_collection.CollectionPositionalEncoding
CollectionAttentionVariant = model_code_collection.CollectionAttentionVariant
CollectionCodeFingerprint = model_code_collection.CollectionCodeFingerprint
CollectionKeyCall = model_code_collection.CollectionKeyCall
CollectionSpecialOp = model_code_collection.CollectionSpecialOp
CollectionDedupPolicy = model_code_collection.CollectionDedupPolicy
CollectionVarietyAxis = model_code_collection.CollectionVarietyAxis
CollectionDedupDecision = model_code_collection.CollectionDedupDecision
CollectionDedupRecord = model_code_collection.CollectionDedupRecord
CollectionRunnableState = model_code_collection.CollectionRunnableState
CollectionRankWorkload = model_code_collection.CollectionRankWorkload
CollectionRunnableFailureKind = model_code_collection.CollectionRunnableFailureKind
CollectionRunnableFailure = model_code_collection.CollectionRunnableFailure
CollectionRunnableRecord = model_code_collection.CollectionRunnableRecord
CollectionPairingKind = model_code_collection.CollectionPairingKind
CollectionPairingTarget = model_code_collection.CollectionPairingTarget
CollectionTrainingPairing = model_code_collection.CollectionTrainingPairing
Fetch = model_code_collection_api.Fetch
Dedup = model_code_collection_api.Dedup
ProbeRunnable = model_code_collection_api.ProbeRunnable
```

## types.viba

模型代码收集被形式化成一份清单：一个模型一条 `CollectionManifestEntry`。取值只能落在有限集合里的概念写成枚举：`CollectionSource` 是一个枚举，`hub_api` 与 `own_registry` 是它的取值，说明这个模型从哪类来源收进来；`CollectionFilter`、`CollectionLicenseState`、`CollectionCodeRole`、`CollectionDedupDecision`、`CollectionRunnableState`、`CollectionPairingKind` 同为枚举，分别表示筛选条件、许可证是否声明、代码角色、去重决定、可跑性结论与训练代码配对规则。抓取、去重、验证与配对各自的产出写成类型：`CollectionDownload` 由 `CollectionCodeFile` 组成，`CollectionFingerprint` 分成 `CollectionConfigFingerprint` 与 `CollectionCodeFingerprint` 两层，`CollectionDedupRecord`、`CollectionRunnableRecord`、`CollectionTrainingPairing` 依次承载去重、可跑性与训练代码配对的结论，并作为 `CollectionManifestEntry` 的字段。

```bash types
import aisp.bench.checkpoint.sample.public as sample

CollectionSource =
  Oneof
  | "hub_api" * { HuggingFace Hub 模型列表接口，主来源；取 model id、下载量、likes、创建时间、library_name、pipeline_tag、tags }
  | "org_page" * { 组织主页，补齐大厂模型；取同一组织下的全部模型 }
  | "paper" * { 论文与发布公告，补齐新架构；取论文中提到的开源实现 }
  | "own_registry" * { 自有模型清单，补齐团队自有的模型；取自有仓库地址与 commit }

CollectionFilter =
  Oneof
  | "text_generation" * { pipeline_tag 属于文本生成类 }
  | "transformers_or_modeling_file" * { library_name 为 transformers，或仓库内有独立的 modeling_*.py }
  | "param_scale" * { 参数量从配置里推断，覆盖从 0.1B 到 1T 的多个量级 }
  | "one_revision_per_model" * { 同一 model id 的不同 revision 只保留一个，默认取 main 分支的最新 commit，并在清单里记下 commit }

CollectionManifestEntry =
  Object
  * $model (sample.Model * { 模型的标识与代码 commit；同一 model id 只留一个 revision })
  * $source (CollectionSource * { 这个模型从哪个来源收进来 })
  * $license (CollectionLicense * { 许可证；决定代码能否入库、能否被下游使用 })
  * $params_b (float * { 参数量，单位 B，从配置里推断；要覆盖从 0.1B 到 1T 的多个量级 })
  * $code_role (CollectionCodeRole * { 这份代码是推理代码还是预训练代码 })
  * $code_role_evidence (list[CollectionCodeRoleEvidence] * { 判定 code_role 的证据，按可靠性从高到低排；必须留下证据，不能靠模型或人猜 })
  * $download (CollectionDownload * { 取到的代码与配置文件，不取权重 })
  * $fingerprint (CollectionFingerprint * { 结构指纹：配置层与代码层两层 })
  * $workspaces (list[CollectionWorkspace] * { 这个模型用过的工作区；一个模型可以对应多个，重试或换依赖版本各开一个 })
  * $dedup ((CollectionDedupRecord | nil) * { 去重决定；还没做去重时给 nil })
  * $runnable ((CollectionRunnableRecord | nil) * { 可跑性验证结论；还没跑时给 nil })
  * $training ((CollectionTrainingPairing | nil) * { 训练代码配对结论；还没判定时给 nil })

CollectionLicense =
  Object
  * $id ((str | nil) * { 许可证标识；仓库没写时给 nil })
  * $state (CollectionLicenseState * { 许可证是否声明；缺失许可证的模型单独标记，不默认纳入语料 })

CollectionLicenseState =
  Oneof
  | "declared" * { 仓库声明了许可证；按这份许可证决定代码能否入库、能否被下游使用 }
  | "missing" * { 仓库没写许可证；单独标记，不默认纳入语料 }

CollectionDownload =
  Object
  * $files (list[CollectionCodeFile] * { 按文件名白名单取到的代码与配置，不下载权重；显式排除 *.safetensors、*.bin、*.pt、*.pth、*.gguf 以及大于阈值的文件；下载完成后校验文件数量与清单一致；进到工作区后原样保留，不做格式化或改写 })
  * $oversized (list[str] * { 因为超过阈值没有取的大文件；进入下载清单时要报警，不要静默跳过 })
  * $failures (list[CollectionFetchFailure] * { 重试有上限，到上限仍然失败的原因按类记在这里 })
  * $resumed (bool * { 这次下载有没有用到断点续传 })

CollectionCodeFile =
  Object
  * $path (str * { 文件在模型目录里的相对路径 })
  * $kind (CollectionFileKind * { 属于白名单里的哪一类 })
  * $sha256 (str * { 文件内容的 sha256；下载器逐个文件记录 })

CollectionFileKind =
  Oneof
  | "config" * { config.json；参数量从这份配置推断，配置层结构指纹也从这里读 }
  | "configuration" * { configuration_*.py；配置类定义 }
  | "modeling" * { modeling_*.py；建模代码，代码层结构指纹从这些文件解析 }
  | "referenced_module" * { modeling_*.py 引用的同仓库 .py 文件；要跟着引用一并取下 }
  | "tokenizer_config" * { tokenizer_config.json；分词器配置 }
  | "generation_config" * { generation_config.json；生成配置 }

CollectionFetchFailure =
  Oneof
  | "network" * { 网络失败；重试有上限，到上限仍然失败就记这一条 }
  | "permission" * { 权限不足 }
  | "not_found" * { 文件不存在 }
  | "license_not_accepted" * { 许可未接受 }

CollectionCodeRole =
  Oneof
  | "inference" * { 推理/建模代码：仓库里只有 modeling_*、configuration_* }
  | "pretrain" * { 预训练代码：仓库里有训练入口、训练框架标记或 README 里的训练说明 }
  | "both" * { 推理代码与预训练代码都在 }
  | "unknown" * { 判定不出；允许存在，但要计入覆盖率缺口 }

CollectionCodeRoleEvidence =
  Oneof
  | "repo_structure" * { 仓库文件结构：只有 modeling_*、configuration_* 的，是推理/建模代码；可靠性高 }
  | "training_entry" * { 训练入口：存在 train*.py、pretrain*.py、finetune*.py、examples/ 下的训练脚本；可靠性高 }
  | "framework_marker" * { 训练框架标记：仓库 tags 或依赖里出现 DeepSpeed、Megatron、FSDP、Accelerate 的训练用法；可靠性中 }
  | "readme_training" * { README 中的训练说明：明确给出预训练或继续训练的步骤；可靠性中 }
  | "weight_release" * { 权重发布形态：只发推理权重与量化权重，通常无训练代码；可靠性低 }

CollectionWorkspace =
  Object
  * $id (str * { 工作区标识；每个模型在一个独立工作区里下载、安装依赖、验证 })
  * $env (str * { 独立依赖环境：虚拟环境或容器镜像，一个工作区一套，互不污染 })
  * $framework_major (str * { transformers 主版本；依赖冲突按主版本分组解决，同组共用一个工作区镜像，不做逐模型钉版本 })
  * $disk_policy (str * { 磁盘配额与清理策略；两者固定，避免 1000 个模型的代码把盘写满 })

CollectionFingerprint =
  Object
  * $config (CollectionConfigFingerprint * { 配置层：从 config.json 能直接读到的 })
  * $code (CollectionCodeFingerprint * { 代码层：需要解析建模文件 })

CollectionConfigFingerprint =
  Object
  * $architectures (list[str] * { 架构类名 })
  * $num_hidden_layers (int * { 层数；组内算距离时权重最高 })
  * $hidden_size (int * { 隐藏维度；组内算距离时权重最高 })
  * $num_attention_heads (int * { 注意力头数 })
  * $num_key_value_heads (int * { KV 头数；组内算距离时权重最高 })
  * $intermediate_size (int * { FFN 维度 })
  * $vocab_size (int * { 词表大小；组内算距离时权重最低 })
  * $max_position_embeddings (int * { 位置编码长度 })
  * $torch_dtype (str * { 权重精度 })
  * $tie_word_embeddings (bool * { 是否共享词嵌入 })
  * $moe ((CollectionMoeSpec | nil) * { MoE 相关字段：专家数、激活专家数、共享专家；不是 MoE 的模型给 nil })
  * $positional_encoding (CollectionPositionalEncoding * { 位置编码类型 })
  * $attention (CollectionAttentionVariant * { 注意力变体 })

CollectionMoeSpec =
  Object
  * $num_experts (int * { 专家数 })
  * $num_active_experts (int * { 激活专家数 })
  * $num_shared_experts (int * { 共享专家的个数 })

CollectionPositionalEncoding =
  Oneof
  | "rope" * { RoPE 及其变体 }
  | "alibi" * { ALiBi }
  | "absolute" * { 绝对位置 }

CollectionAttentionVariant =
  Oneof
  | "mha" * { MHA，多头注意力 }
  | "gqa" * { GQA，分组查询注意力 }
  | "mqa" * { MQA，多查询注意力 }
  | "mla" * { MLA，多头潜在注意力 }
  | "linear" * { 线性注意力 }
  | "sliding_window" * { 滑动窗口注意力 }

CollectionCodeFingerprint =
  Object
  * $module_classes (list[str] * { 模块类名序列：从 __init__ 里按定义顺序抽出子模块类名 })
  * $calls (list[CollectionKeyCall] * { 前向路径中的关键调用，按出现顺序 })
  * $special (list[CollectionSpecialOp] * { 特殊计算 })

CollectionKeyCall =
  Oneof
  | "attention" * { 注意力计算 }
  | "norm" * { 归一化 }
  | "mlp" * { 前馈网络 }
  | "residual" * { 残差连接 }
  | "routing" * { MoE 路由 }

CollectionSpecialOp =
  Oneof
  | "custom_kernel" * { 自定义 kernel 调用 }
  | "fused_op" * { 融合算子 }
  | "quantization_branch" * { 量化分支 }

CollectionDedupPolicy =
  Object
  * $threshold (float * { 组内加权距离小于阈值的视为重复，只保留一个代表；初始值 0.15，必须在覆盖度报告上标定后再用 })
  * $weights (dict[str, float] * { 配置层每个维度的权重，按该维度对 IO 的影响排：层数、KV 头数、隐藏维度最高，词表大小最低；组内先按对数缩放再归一化，再加权求距离 })
  * $variety (list[CollectionVarietyAxis] * { 保留策略是最大边际覆盖，不是每组留一个：优先保留能带来这些新维度的样本 })

CollectionVarietyAxis =
  Oneof
  | "scale" * { 新规模量级 }
  | "positional_encoding" * { 新位置编码 }
  | "attention_variant" * { 新注意力变体 }
  | "moe" * { MoE 与非 MoE 各留 }

CollectionDedupDecision =
  Oneof
  | "kept" * { 保留；保留策略是最大边际覆盖，优先留能带来新维度的样本 }
  | "dropped" * { 丢弃；组内距离小于阈值的重复样本，只保留一个代表 }

CollectionDedupRecord =
  Object
  * $group (str * { 去重分组：同一 architectures 且代码层关键调用序列一致的模型同组；去重只作用于同一评估集内部，训练侧与推理侧关心的结构维度不同，不能跨评估集删 })
  * $decision (CollectionDedupDecision * { 这个样本是保留还是丢弃 })
  * $dropped_by ((sample.Model | nil) * { 丢弃时指向代表样本；保留时给 nil })

CollectionRunnableState =
  Oneof
  | "yes" * { 能跑：这次验证没有失败的步骤 }
  | "no" * { 不能跑：验证失败 }
  | "partial" * { 部分跑通：有的步骤成功、有的失败，失败项按类记在 failures }

CollectionRankWorkload =
  Oneof
  | "forward" * { 跑一次前向 }
  | "prefill" * { 跑一次预填充 }

CollectionRunnableFailureKind =
  Oneof
  | "timeout" * { 超时；每步都设了超时，超时单独归类 }
  | "oom" * { 显存不足 }
  | "assertion" * { 断言失败 }
  | "missing_dependency" * { 依赖缺失 }

CollectionRunnableFailure =
  Object
  * $kind (CollectionRunnableFailureKind * { 按类分开记，不混成一个失败 })
  * $step (str * { 失败发生在验证的哪一步 })
  * $summary (str * { 错误摘要 })

CollectionRunnableRecord =
  Object
  * $state (CollectionRunnableState * { 这份代码在当前环境下能不能跑起来；只判能不能跑，不测性能，也不测数值正确性 })
  * $workload (CollectionRankWorkload * { 每个 rank 只跑一次：前向或预填充，输入用固定维度与尺寸的假张量，batch 与序列长度取该模型配置允许的小值 })
  * $ranks (int * { 起的 rank 数；固定取一个能触发多 rank 分支的小值，例如 2 或 4，不为每个模型动态决定。只跑 world_size=1 覆盖不到按 world_size、rank、local_rank 分支的路径（分片加载、张量并行切分、通信初始化） })
  * $backend (str * { 分布式后端：初始化真实的分布式环境，把 torch.distributed 的后端换成 mock——init_process_group 用 gloo 或自定义的假后端，new_group、get_world_size、get_rank、all_reduce 等按预置的 rank 数返回；返回值的张量维度与 dtype 必须正确，否则代码会在后续计算里崩，测出来的失败是假的 })
  * $concurrency (int * { 这次运行的并发，固定为 1：每个 rank 单独起进程、分时占用同一张 GPU，rank 0 跑完释放显存 rank 1 再跑；不要求真并行，也就不要求多卡，但必须标明 })
  * $failures (list[CollectionRunnableFailure] * { runnable_detail：失败步骤与错误摘要，按类分开记 })

CollectionPairingKind =
  Oneof
  | "same_org" * { 同组织下存在与推理模型同架构族的预训练实现，优先配对 }
  | "same_architecture" * { 配置里 architectures 字段相同的模型，按组织与发布时间就近配对 }
  | "external_link" * { README 或模型卡引用了他处的训练仓库，记为外链配对 }
  | "unpaired" * { 都找不到，记为 unpaired，写进缺口清单 }

CollectionPairingTarget =
  Object
  * $repo (str * { 训练代码的仓库地址 })
  * $commit ((str | nil) * { 钉到具体一份代码的 commit；不知道时给 nil })

CollectionTrainingPairing =
  Object
  * $kind (CollectionPairingKind * { 按哪条规则配上的；配对率是验收指标之一，不允许只统计配对成功的那部分 })
  * $target ((CollectionPairingTarget | nil) * { 配上的训练代码；unpaired 时给 nil })
```

## 基本操作

1. 抓取：按来源的优先级取 model id，用筛选条件过滤，只下载代码与配置并逐个文件记 sha256，同时记下许可证、参数量、代码角色与判定证据。
2. 去重：按结构指纹分架构族，组内算加权距离，决定每条记录是 kept 还是 dropped，重复的只留一个代表。
3. 跑一遍：在 mock 的分布式环境里，每个 rank 单独起进程、分时占用同一张 GPU，只跑一次前向或预填充，超时、OOM、断言失败、依赖缺失分开记。

## apis.viba

```bash apis
import aisp.bench.checkpoint.model_code_collection.types as collection

Fetch =
     list[collection.CollectionManifestEntry]
  <- $sources (list[collection.CollectionSource] * { 这次从哪几个来源收，按优先级从高到低：主来源是 HuggingFace Hub 的模型列表接口，组织主页、论文与发布公告、自有模型清单用来补齐 })
  <- $filters (list[collection.CollectionFilter] * { 这次用哪几条筛选条件；初始值固定，之后按覆盖度报告调整 })
  <- {
    抓取：按来源取 model id，按筛选条件过滤，只取代码与配置不取权重，逐个文件记 sha256，记录许可证；判定代码角色并留下证据，每个模型在独立工作区里下载并原样保留。返回每个模型一条清单记录，其中 dedup、runnable、training 还是 nil
  }

Dedup =
     list[collection.CollectionManifestEntry]
  <- $entries (list[collection.CollectionManifestEntry] * { 抓取得到的全部清单记录；去重只在同一评估集内部做 })
  <- $policy (collection.CollectionDedupPolicy * { 组内距离的阈值、各维度的权重与保留策略 })
  <- {
    去重：同一 architectures 且代码层关键调用序列一致的记录分为一组，组内按配置向量算加权距离；距离小于阈值的只留一个代表。返回同一批记录，每条写上 dedup；dropped 的记录留在清单里，只是不再进入可跑性验证
  }

ProbeRunnable =
     collection.CollectionRunnableRecord
  <- $entry (collection.CollectionManifestEntry * { 要验证的那条记录；dropped 的记录不跑 })
  <- {
    跑一遍：初始化真实的分布式环境但把后端换成 mock，每个 rank 单独起进程、分时占用同一张 GPU，每个 rank 只跑一次前向或一次预填充；每步设超时，失败按超时、OOM、断言失败、依赖缺失分开归类。返回这条记录的可跑性结论，结论里标明并发为 1
  }
```
