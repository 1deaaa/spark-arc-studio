# ArcPen 低成本执行 Agent 工作流

## 0. 执行者协议

你是 ArcPen 后训练项目的稳定执行者。你的优势是严格、低成本、能长时间重复实验；你不负责临场发明研究路线。必须按本文件推进，每一步保留证据，不得跳过门槛，不得同时改变多个不能归因的变量。

### 0.1 五条铁律

1. **没有冻结基线，不开始训练。**
2. **没有数据 manifest 和泄漏报告，不加载训练集。**
3. **BF16/16-bit LoRA 是质量主线；INT8 必须先通过配对资格试验；Q4 QLoRA 只允许作为明确标记的显存极限消融。**
4. **一次迭代只验证一个主要假设。**补数据、改 LoRA、改训练长度、换偏好算法不能同时做。
5. **评测分下降或奖励异常时立即停止，不用更多 step 赌反弹。**

### 0.2 你可以自行决定的事项

- 重试无副作用的下载、编译、评测和日志采集；
- 按预设网格运行下一个实验；
- 对确定性失败进行归类；
- 根据本文件的决策表选择下一条已授权分支。

### 0.3 必须上报而不能自行决定的事项

- 改变 10,000 条数据配额或 train/dev/test 切分；
- 使用未授权真实作品或用户数据；
- 从 Qwen3.5-9B 切换基座；
- 放宽 accepted 文学标准；
- 进入在线 RL；
- 修改 SparkArc 正式运行协议以适配模型错误；
- test_blind 泄漏、评委失效、基座/Unsloth 官方兼容性发生重大变化。

## 1. 实验目录与记录

为每个实验创建独立目录：

```text
arcpen-runs/<run_id>/
  RUN.md
  environment.json
  data_manifest.json
  config.yaml
  logs/
  checkpoints/
  eval/
  quantization/
  artifacts.json
  decision.md
```

`run_id` 格式：`YYYYMMDD-stage-model-data-config-seed`。禁止覆盖已有 run。`RUN.md` 首先写：假设、唯一主要变量、基线 run、预期最小效应、早停条件。

每次运行记录：

- GPU、VRAM、驱动、CUDA、PyTorch、Transformers、TRL、PEFT、Unsloth、unsloth_zoo、llama.cpp commit；
- 基座仓库与精确 revision；
- 数据 manifest/hash、prompt/hash、tool schema/hash；
- seed、完整命令、环境变量白名单；
- 峰值 VRAM、wall time、非 padding token、step、loss、学习率；
- checkpoint hash、adapter hash、merged hash、GGUF hash；
- 完整评测版本和结果。

## 2. 阶段 0：环境与硬件资格检查

### 2.1 创建隔离环境

不要使用全局 Python，也不要使用 `server/.runtime/python/`。使用负责人指定的 conda/venv/uv 环境，并记录 Python 绝对路径。安装最新版 Unsloth 后锁定精确版本，不在一个实验中间升级。

Qwen3.5 要求 Transformers v5。安装后做 import 和版本检查，再加载模型。首次 Mamba Triton kernel 编译耗时不能误判为训练卡死。

### 2.2 精度硬检查

加载配置必须满足：

```text
load_in_4bit = false
load_in_16bit = true
full_finetuning = false
bf16 = true（硬件支持时）
```

若日志出现 4-bit base weights、bnb 4-bit model load 或 QLoRA，立即终止并标记 `invalid_training_precision`。

`adamw_8bit` 允许使用，它只压缩优化器状态，不等于 4-bit 模型训练。

### 2.3 最小烟雾测试

用 8 条非正式样本完成：加载、chat template、前向、反向、保存 adapter、重新加载、合并、生成。逐 token 检查 label mask：

- system/user/tool 输入标签为 ignore；
- assistant 正文和 assistant tool-call 目标有损失；
- 工具结果默认作为上下文，不把结果文本训练成 assistant；
- EOS 被训练；
- 不存在全 `-100` 或 prompt token 泄漏到标签。

失败则停止，不进入数据/超参试验。

### 2.4 显存探测

固定 rank 16、batch 1、gradient checkpointing。本地 15GB 的 9B INT8 与云端单 vGPU 32GB 的 27B INT8/FP8 资格试验均从 2K 开始，再依次试 4K、8K；只有仍有明确余量才试 16K/32K。每档跑 3 个 step 并记录前向、反向和峰值显存。若 OOM，按顺序：

1. 先保持 BF16 base；
2. batch 保持 1；
3. 减少该阶段 max sequence；
4. 使用梯度累积；
5. 使用多卡/FSDP/更大显存机器；
6. 若当前精度的目标长度仍放不下，进入 2.5 节的精度配对资格试验；
7. 仍不够则上报硬件阻塞，Q4 不得被静默替换成主线。

禁止为了跑通偷偷截断样本或切换 QLoRA。日志必须区分：`load_in_8bit=True` 是冻结基座的 BitsAndBytes `LLM.int8()`；`optim="adamw_8bit"` 只压缩优化器状态；GGUF `Q8_0` 只用于部署评测，三者不得混写成“Q8 训练”。

### 2.5 INT8/FP8 精度资格试验

使用同一份 1,000 条训练子集、同一初始权重、seed、rank、alpha、学习率、有效 batch、更新 token 数和代表性序列长度，运行：

- `P0`：BF16/16-bit LoRA；
- `P1`：BitsAndBytes INT8 LoRA；
- `P2`：Unsloth FP8 LoRA，仅在 GPU 原生支持且当前版本能加载 Qwen3.5 时运行；
- `P3`：Q4 QLoRA，仅作消融，不因显存更低自动晋级。

每个候选必须完成加载、固定输入前向、至少 50 个训练 step、验证 loss、adapter 保存/恢复、继续训练、合并、导出、独立进程重载和固定集生成。FP8 checkpoint 若只能推理、不能合并，记为“不具备训练生命周期”，不能靠手工绕过后晋级。

在同一 `dev_fast` 上报告协议成功率、长度命中率、事实冲突率、文学成对盲评、通用能力护栏、峰值显存和 tokens/s。资格门槛：相对 BF16 的协议成功率下降不超过 1 个百分点，文学长度匹配胜率的 95% 置信区间不得显示实质劣势，事实冲突率不得增加超过 2 个百分点，且所有生命周期步骤通过。未过门槛就回到 BF16 或缩小模型，不用更长训练掩盖精度问题。

FP8 还要额外记录 GPU 型号与计算能力，并检查 checkpoint 中 scale tensor 在保存、恢复和合并前后未丢失。T4 不运行 FP8。社区 FP8 推理 checkpoint 不直接进入本试验，除非框架明确声明可训练并通过上述生命周期。

### 2.6 当前两套硬件的分工

**本地约 15GB 可用显存：**运行 Qwen3.5-9B INT8 LoRA，初始 `max_seq_length=2048`、batch 1、rank 16。先完成 8 条烟雾测试，再运行 200 条微型配对；只有峰值显存至少保留 1GiB 才升到 4K。相同短序列尽可能补一个 BF16 LoRA 质量锚点；若 BF16 OOM，不得把 INT8 自身训练前后的比较写成 BF16 非劣结论。

**云端单 vGPU 32GB（已核验）：**该容器只暴露 1 张 RTX 4080 SUPER、32,760MiB、计算能力 8.9 的 CUDA 设备。27B 按 `INT8 2K -> FP8 2K -> Q4 2K` 的顺序分别执行 8 条、3 step 资格试验；峰值显存超过 30GiB、发生 CPU offload、生命周期失败或吞吐低于预设经济门槛，立即判该精度不适合正式训练。只有 INT8/FP8 留出至少 2GiB 余量并通过 2.5 节，才允许扩大到 50 step；否则 27B 正式实验使用 Q4 QLoRA，并把 9B INT8/BF16 作为量化质量参照。

CPU/RAM offload 仅允许定位兼容性问题，不允许作为论文主实验或正式数据生产配置。

## 3. 阶段 1：冻结评测与基线

### 3.1 数据审计

输入：`instruction.md` 产出的 manifest。输出 `data_audit.md`，必须包含：

- 各主类精确计数；
- 剧本/小说、模态、难度、长度分布；
- 项目级 split 检查；
- MinHash、最长公共短语、embedding 近邻泄漏；
- tool schema 和消息 schema 验证；
- 完整末尾/EOS/保存回执检查；
- 许可和 provenance 缺失条数；
- 随机 100 条人工可读抽查。

任何硬失败不允许自动修补进 accepted；退回数据合成流程生成新 revision。

### 3.2 四个初始基线

至少运行：

- `B0`: Qwen3.5-9B BF16 + 完整 harness；
- `B1`: Qwen3.5-9B Q8_0 + 完整 harness；
- `B2`: Qwen3.5-9B Q4_K_M + 完整 harness；
- `B3`: Qwen3.5-9B BF16 + 最小 harness。

推理默认 `enable_thinking=false`。温度、top-p、top-k、max output 在所有可比 run 中相同。创意评测至少使用两个固定 seed；确定性协议评测使用 temperature 0 或等价确定性设置，文学评测使用产品候选设置。

### 3.3 基线产物

输出 `baseline_report.md`：

- 确定性、文学、系统三层指标；
- 按任务桶分解，不只报总分；
- BF16→Q8→Q4 的退化；
- 失败样本 ID、原始输出、validator 证据；
- 100 个错误的人工归因抽样；
- 冻结的最小可检测效应。

## 4. 阶段 2：SFT 超参筛选

### 4.1 只用训练集的 10% 做 screening

保持项目级分层，选 1,000 条，不得从 dev/test 抽样。max sequence 使用 2.4/2.5 节在当前硬件通过的代表长度，不预设 8K；单种子、最多 300 step。

运行四格：

| 配置 | rank | alpha | 学习率 |
|---|---:|---:|---:|
| S1 | 16 | 16 | 5e-5 |
| S2 | 16 | 16 | 1e-4 |
| S3 | 32 | 32 | 5e-5 |
| S4 | 32 | 32 | 1e-4 |

共同配置：LoRA 目标为 q/k/v/o/gate/up/down，dropout 0，bias none，默认 BF16，`adamw_8bit`，warmup ratio 0.03，cosine，gradient checkpointing `unsloth`。只有 2.5 节已证明 INT8/FP8 非劣时，才可用对应精度重复同一四格。

### 4.2 screening 选择规则

在 120 题 `dev_fast` 上比较：

1. 协议硬失败率；
2. 保存成功率；
3. 文学盲评代理；
4. 通用能力护栏；
5. 峰值 VRAM 和吞吐。

若两个配置差异低于噪声，选 rank 更小/学习率更低的配置。训练 loss 更低不能单独决定胜者。

若所有配置都比基线差：先检查标签 mask、chat template、数据截断和数据质量；不得直接扩大 rank 或训练轮数。

## 5. 阶段 3：SFT v1 主训练

### 5.1 训练课程

按 sequence length 分三段，但保持同一 adapter 连续训练：

1. 8K 主体：约 70% 数据；
2. 16K 难例：约 25% 数据，学习率降为上一段的 0.5-0.7；
3. 32K 压力样本：约 5%，学习率再降，若硬件不允许则上报，不可静默删掉。

每段训练前重新验证：样本总 token 未截断关键尾部；tool-call 与 tool-result 边界完整；assistant-only mask 正确。

### 5.2 checkpoint 评测

按有效 token 间隔保存，不按样本数猜测。每个 checkpoint 运行 `dev_fast`。满足任一条件早停：

- 连续 3 次协议/文学综合不升；
- 通用护栏下降 >3 个百分点；
- 平均输出长度增长 >20% 且长度命中不升；
- 重复率、模板化结尾率或事实矛盾率显著恶化；
- loss 非有限、梯度爆炸或 KL 代理突变。

### 5.3 选择与三种子复现

单种子选出 checkpoint 后，用两个额外 seed 复现同配置。三个 seed 都运行完整 `dev_public`。报告均值、标准差和任务级 bootstrap CI。

不能只选最幸运 seed 进入后续阶段。发布 checkpoint 选择规则必须在看到 `test_blind` 前冻结。

## 6. 阶段 4：合并、量化与端到端回归

### 6.1 三点导出

对每个晋级 checkpoint 保存：

- merged F16/BF16；
- Q8_0；
- Q4_K_M。

保留 tokenizer、chat template、generation config 和 GGUF metadata。导出后做 hash 与可加载性检查。

### 6.2 量化回归

在相同 prompt、seed 和 harness 上跑完整 dev。逐维计算：

- 格式/工具准确率差；
- 事实一致性差；
- 目标长度偏差；
- 文学成对胜率；
- 输出截断、乱码、重复；
- 吞吐、TTFT、RAM/VRAM。

若 Q4 文学损失 >8 个百分点或协议成功率下降 >2 个百分点：

1. 核对 chat template 与量化导出；
2. 比较 Q8 确定退化曲线；
3. 尝试官方支持的更高质量 Q4 变体或保留 Q5/Q6 备选；
4. 不允许用 BF16 结果替代 Q4 部署结论。

## 7. 阶段 5：错误归因与 SFT 数据闭环

### 7.1 每轮只选一个主错误桶

从 dev 失败中统计：

`protocol`、`continuity`、`length`、`literary`、`mode_confusion`、`tool_recovery`、`quantization_only`、`judge_uncertain`。

选择满足以下条件的一个主桶：样本量足够、影响大、置信度高、SFT 可修复。每轮补 200-800 条，保持旧数据累计，不替换整个数据集。

### 7.2 补数据后训练

- 从上一最佳 SFT adapter 继续低学习率训练，和“从基座用新全集重训”做小规模对照；
- 只在 dev 验证目标桶是否提升；
- 同时检查邻近桶和通用能力是否退化；
- 连续两轮补数对目标桶的提升都低于最小效应，标记 `sft_saturated`。

### 7.3 禁止的 ReAct 行为

- 看到一个坏例子就改全局 prompt；
- 看到 loss 高就多训 epoch；
- 文学分不升就提高输出长度；
- 同时补数据、换 rank、换学习率和换评委；
- 用 test_blind 挑错误桶；
- 删除模型失败样本，只保留容易题。

## 8. 阶段 6：偏好数据与 DPO/SimPO

### 8.1 进入条件

只有 `sft_saturated` 且问题属于稳定主观偏好或完成度时进入。协议 schema 错误优先继续 SFT/验证器，不用 DPO 掩盖。

### 8.2 on-policy 候选生成

从冻结的 3,000 个 preference prompt 出发，使用当前 SFT 模型每题采样 4 个候选，共 12,000 个。候选必须来自学生当前分布，不使用教师预制坏答案。

评审流程：硬验证 -> 长度匹配 -> 两个异源强评委 A/B 交换 -> 分歧过滤 -> 形成 2,400 个训练对和 600 个校准/评测题。

配额：文学 1,400、连续性 400、长度 300、工具/格式恢复 300。chosen/rejected 长度比优先位于 `[0.85, 1.18]`；超出必须说明长度本身是偏好依据。

### 8.3 DPO 主实验

- 从最佳 SFT checkpoint 初始化；
- LoRA 继续训练，BF16 base；
- `beta ∈ {0.05, 0.1, 0.2}` 小网格，先 20% 数据 screening；
- 1 epoch 起步；
- reference 使用 PEFT/Unsloth 支持的隐式参考方式，记录实现；
- 每 20% epoch 跑 `dev_fast`；
- 监控 chosen/rejected reward margin、平均长度、KL 代理和通用护栏。

### 8.4 SimPO 消融

仅在 DPO 主实验稳定后运行。它的长度归一化和无参考模型特点适合验证长度偏差，但不能假设必然更好。使用相同偏好对、近似计算预算和相同 checkpoint 选择规则。

### 8.5 偏好阶段失败条件

任一满足即判该 run 失败：

- 文学代理升但人类小样本不升；
- 平均输出长度增长 >15% 且 length-controlled 胜率不升；
- 多样性显著下降或同一类收束快速增多；
- 协议/保存成功率下降 >1 个百分点；
- 通用护栏下降 >3 个百分点；
- 偏好 reward 上升而 oracle 矛盾率上升。

## 9. 阶段 7：在线 RL 资格审查

不要自行开始 RL。先提交 `rl_readiness.md`，逐条给证据：

- SFT 两轮补洞均饱和；
- DPO/SimPO 未解决同一缺陷；
- 4-6 个 on-policy 候选存在稳定质量差；
- GenRM 人类成对准确率 ≥75%；
- 长度匹配子集 ≥72%；
- A/B 交换一致率 ≥90%；
- 重复判分一致率 ≥85%；
- 控制人类质量后 reward 与长度无明显虚假相关；
- 有回滚 checkpoint 和完整 BF16/Q4 eval；
- 已获得负责人明确批准。

少一项都不开始。

## 10. 阶段 8：经批准的 GRPO/GSPO 小试

### 10.1 实现边界

- 采用 Unsloth 当前 Qwen3.5 支持路径；按官方说明关闭 fast vLLM inference，使用 Unsloth inference；
- BF16/16-bit LoRA，不用 4-bit QLoRA；
- 先 8K-16K，`num_generations=4`；稳定后最多 6；
- prompt 1,200-2,000 个；
- 从最佳 SFT+DPO 或最佳 SFT 初始化，两者做对照；
- 不直接声称复现 Writing-Zero BRPO，除非实现和公式完全一致。

### 10.2 奖励流水线

1. 运行确定性硬门禁；
2. 硬失败总 reward=-1；
3. 通过后计算写作、连续性、harness、格式、长度、风格六分量；
4. 每分量组内归一化至 `[-1,1]`；
5. 按主报告初始权重组合；
6. 写出每个样本的分量、证据和最终 reward；
7. 每个 checkpoint 重新做独立评委评测，训练 reward 不能充当 eval。

长度 reward 规则：目标 ±15% 内平台，不因更长继续增加；超过后平滑下降，±30% 仍不视作硬失败；超长注水和中途截断分别由文学/完整度惩罚。

### 10.3 RL 早停

每 25-50 update 检查：

- proxy reward 与独立 eval 是否同时上升；
- KL、entropy、长度、重复率、拒绝率；
- 某一 reward 分量是否支配总方差；
- 输出是否出现评委偏爱的固定措辞或结构；
- 工具调用是否变多但成功率不升。

独立 eval 连续两次不升、proxy 与人类方向相反、或任何硬指标显著退化时立即停止并回滚。

## 11. 阶段 9：2×2 harness/model 消融

### 11.1 四个单元

- M0H0：通用 Qwen3.5-9B + 最小安全 harness；
- M0H1：通用 Qwen3.5-9B + 完整 SparkArc harness；
- M1H0：ArcPen-9B + 同一最小 harness；
- M1H1：ArcPen-9B + 完整 SparkArc harness。

四组使用同量化、同解码参数、同任务、同 validator。H0 只移除 PreWrite/StoryMemory/统一布局等目标组件，不移除文件安全和结果核验，也不故意给错误工具。

### 11.2 统计

计算：模型主效应、harness 主效应、交互效应。按剧本/小说、工具/纯正文、短/长上下文分层。用任务级 bootstrap 95% CI；有条件时用混合效应模型，以任务/项目为随机效应。

只有 `Δinteraction` 的置信区间支持正值时，论文才能强声称 1+1>2；否则应如实报告两个独立增益或某一层主导。

## 12. 阶段 10：test_blind 与人类评测

test 只在下列里程碑运行：基线冻结、SFT v1、最终偏好模型、最终 RL（若有）、最终 Q4。中间超参不跑 test。

120 题核心集由至少 3 名人类评委做成对盲评。交换顺序、隐藏模型名和长度。记录胜/平/负、理由和置信度。计算评委一致率/Krippendorff's alpha；分歧题单独分析，不强行平均。

最终报告必须同时给原始胜率和 length-controlled/长度匹配胜率。

## 13. 阶段 11：9B 到 27B

9B 达到晋级门槛后才开始：

1. 冻结相同数据/评测版本；
2. 先 500 条烟雾和 2,000 条规模点；
3. 重新筛 rank `{16,32,64}` 与学习率 `{2e-5,5e-5}`，单种子 screening；
4. 选择后全量，最终关键配置 3 种子；
5. 不迁移 9B adapter 权重；
6. 重做 BF16/Q8/Q4 回归和 2×2 消融；
7. 比较每单位训练 token 的边际收益，而不只比较绝对分。

硬件边界：27B 的 INT8/FP8 权重本体约 26-28GiB。单 vGPU 32GB 可容纳权重并留出约 4-6GiB 给运行时，但该余量仍会被激活、adapter、量化元数据和长序列迅速消耗，因此先做正式资格试验，再决定能否进行全量 SFT/DPO/RL。48GB 单卡可使 INT8/FP8 长度课程更从容；正式 BF16 LoRA 预算按约 56-80GB 起步，并由目标序列长度实测修正。官方 `Qwen3.5-27B-FP8` 默认视为推理发布物，除非当前训练栈通过 2.5 节全部生命周期验收。

若 27B 基线已经达到 9B ArcPen 水平，仍要比较 27B ArcPen 的增益；不能把规模提升冒充后训练收益。

## 14. 决策表

| 观察 | 结论 | 下一步 |
|---|---|---|
| 格式/工具失败集中 | SFT 协议覆盖不足 | 补相应轨迹，不上 RL |
| 事实冲突但检索结果正确 | 证据利用不足 | 补对比难例/连续性 SFT |
| 模型没有拿到事实 | harness/上下文问题 | 修复上游，模型训练暂停 |
| 输出普遍过短且数据也短 | 长度分布问题 | 补目标长度 SFT |
| 输出长度达标但注水 | 文学偏好问题 | 长度匹配偏好对/DPO |
| 文学评委高分、人类不升 | judge 偏差 | 校准评委，不继续优化 |
| BF16 好、Q4 差 | 量化问题 | 调量化，不重复训练掩盖 |
| SFT 两轮饱和、DPO 仍有长程缺陷 | 潜在 RL 候选 | 提交资格审查 |
| reward 升、独立 eval 降 | reward hacking | 立即停 RL、回滚 |
| 通用能力下降 >3pp | 过拟合/灾忘 | 降 LR/epoch，增加通用保持数据消融 |

## 15. 每轮 ReAct 模板

每轮严格填写：

```text
观察：只列日志和评测事实。
归因候选：最多 3 个，按证据排序。
可区分实验：只改变 1 个主要变量。
成功阈值：运行前写出。
失败阈值：运行前写出。
执行：记录 run_id 和完整配置。
结果：包含置信区间与分桶结果。
决定：晋级/回滚/补数据/上报，四选一。
```

不得在“决定”里写“继续观察”而无限训练。证据不足时运行更小的区分实验，不运行更大的主训练。

## 16. 最终发布包

ArcPen-9B 候选发布前必须包含：

- 模型卡：基座、许可、适用/不适用范围、thinking 设置；
- BF16 adapter、合并模型 hash；
- Q8/Q4 GGUF 与 tokenizer/chat template；
- 数据卡与不可公开数据说明；
- 完整训练配置、环境锁、三个 seed；
- dev/test、人类评测、2×2 消融、量化回归；
- 已知失败案例；
- SparkArc 兼容的 prompt/tool schema 版本；
- 回滚模型与最低运行资源；
- 论文复现实验索引。

只有 Q4 在完整 SparkArc harness 中通过最终门槛，才能命名为 `ArcPen-9B-v1`。BF16 表现好但 Q4 未通过的模型只能标记为研究 checkpoint。
