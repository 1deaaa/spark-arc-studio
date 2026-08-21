# ArcPen 后训练来源台账

> 最后核验：2026-08-22  
> 证据等级：A = 论文/官方模型卡/官方文档；B = 官方仓库 issue 或可复现实验报告；C = 社区经验，仅用于形成假设。

本文件只记录可追溯证据。推理量化结果不得冒充训练稳定性证据，框架宣称的显存与 loss 结果不得冒充 ArcPen 任务质量结果。

## 1. Qwen3.5 与官方模型发布

| 等级 | 来源 | 本项目采用的事实 | 边界 |
|---|---|---|---|
| A | [Qwen3.5 官方集合](https://huggingface.co/collections/Qwen/qwen35) | 官方尺寸与 checkpoint 清单；FP8 包含 27B、35B-A3B、122B-A10B、397B-A17B | 集合中没有官方 0.8B/2B/4B/9B FP8 |
| A | [Qwen3.5-9B 模型卡](https://huggingface.co/Qwen/Qwen3.5-9B) | 9B 架构、上下文、推理与工具调用说明 | 模型卡指标不是微调显存基准 |
| A | [Qwen3.5-27B 模型卡](https://huggingface.co/Qwen/Qwen3.5-27B) | 27B dense 基座信息与官方使用方式 | 不能由参数量直接推断训练一定可用 |
| A | [Qwen3.5-27B-FP8 模型卡](https://huggingface.co/Qwen/Qwen3.5-27B-FP8) | block size 128 的细粒度 FP8；官方称指标近似原模型；列出 Transformers/vLLM/SGLang/KTransformers 兼容性 | 内容主要面向推理/服务，不证明 PEFT 训练、合并、再导出完整可用 |
| B | [9B 官方仓库的 FP8 请求讨论](https://huggingface.co/Qwen/Qwen3.5-9B/discussions/5) | 社区仍在请求官方 9B-FP8，可辅助确认官方缺口 | 评论中的“无损”是个人推理观察，不作为训练证据 |

## 2. INT8、QLoRA 与训练精度

| 等级 | 来源 | 本项目采用的事实 | 边界 |
|---|---|---|---|
| A | [LLM.int8() 论文](https://arxiv.org/abs/2208.07339) | 将异常值特征分离到 16-bit 计算，其余执行 8-bit 矩阵乘 | 主要目标是大模型推理与前向计算 |
| A | [BitsAndBytes LLM.int8() 文档](https://huggingface.co/docs/bitsandbytes/main/en/reference/nn/linear8bit) | `Linear8bitLt`、异常值阈值、INT8 权重保存与混合精度计算机制 | `load_in_8bit` 不等于 GGUF Q8，也不等于 8-bit optimizer |
| A | [Transformers BitsAndBytes 量化文档](https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes) | 8/4-bit 训练只支持额外参数，冻结量化基座 | 不支持把量化基座当普通全参数训练模型 |
| A | [QLoRA 论文](https://arxiv.org/abs/2305.14314) | 表 3：GLUE 中 BF16 LoRA/INT8 LoRA 均为 88.8；T5-11B Super-NaturalInstructions 均为 60.7；4-bit NF4 的方法依据 | 非 Qwen3.5、非 Gated DeltaNet、非长篇文学或工具轨迹；不能宣称 Qwen3.5 已被证明无损 |
| A | [HALO：低精度优化论文](https://arxiv.org/abs/2501.02625) | 在其 PEFT 任务上，BF16 LoRA 与专门设计的 FP8/INT8 训练接近，说明 8-bit 训练可行但依赖算法 | HALO 不是 BitsAndBytes/Unsloth 的直接等价实现 |

截至核验日，未找到 Qwen3.5-9B 或 27B 在同一数据、超参、seed 与训练 token 下对比 BF16 LoRA、BitsAndBytes INT8 LoRA、Unsloth FP8 LoRA 的严格公开基准。该空白必须由 ArcPen 的精度资格试验补齐。

## 3. Unsloth 与 FP8 LoRA

| 等级 | 来源 | 本项目采用的事实 | 边界 |
|---|---|---|---|
| A | [Unsloth Qwen3.5 微调指南](https://unsloth.ai/docs/models/qwen3.5/fine-tune) | 官方 Qwen3.5 SFT 加载、LoRA target、2K 起步、OOM 调整和 RL 注意事项 | 示例主线使用 16-bit LoRA，未给出 Qwen3.5 FP8 SFT 质量基准 |
| A | [Unsloth FP8 强化学习文档](https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide/fp8-reinforcement-learning) | `load_in_fp8=True`；冻结基座/激活 FP8、LoRA 与反向 BF16；支持 L4/Hopper/RTX 40/50 等；T4 不支持；展示 BF16/FP8 SFT loss 曲线；报告 Qwen3-8B 约节省 8GB | 框架自测，主流程聚焦 RL；loss 接近不等于 ArcPen 文学、协议和长上下文指标非劣 |
| A | [Unsloth Qwen3 通用微调指南](https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune) | 区分 `load_in_8bit`、`load_in_4bit` 与完整 16-bit 加载 | Qwen3 与 Qwen3.5 架构支持不能无条件互推 |
| A | [Unsloth LoRA 超参指南](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide) | LoRA target、rank/alpha、completion-only loss 等实验起点 | 建议值必须经 ArcPen dev 集筛选 |
| A | [Unsloth 多 GPU 指南](https://unsloth.ai/docs/basics/multi-gpu-training-with-unsloth) | 大模型可用 `device_map="balanced"` 做模型分片；DDP/FSDP 与模型分片是不同内存语义 | 没有 Qwen3.5-27B INT8/FP8 在双 16GB 上的官方成功基准，必须实测 |

## 4. FP8 工程风险记录

以下来源用于制定生命周期验收，不代表对应问题在当前最新版必然仍存在。

| 等级 | 来源 | 风险信号 | ArcPen 对策 |
|---|---|---|---|
| B | [Transformers #46736](https://github.com/huggingface/transformers/issues/46736) | FP8 checkpoint 与 PEFT/量化训练保护逻辑可能阻止 LoRA 训练 | 锁版本并验证加载、前反向、保存、恢复、合并、重载 |
| B | [LLaMA-Factory #10328](https://github.com/hiyouga/LlamaFactory/issues/10328) | Qwen3.5-27B-FP8 的 LoRA 合并链路出现失败报告 | 不把“能训练 adapter”当作可交付；合并和再部署是硬门槛 |
| B | [Unsloth #6200](https://github.com/unslothai/unsloth/issues/6200) | Qwen FP8 加载曾出现 scale tensor 丢失并导致极端 perplexity | 对 scale tensor、固定 logits、PPL/KLD 做加载前后校验 |
| B | [Unsloth #3902](https://github.com/unslothai/unsloth/issues/3902) | RTX 50/CUTLASS FP8 初始化存在过兼容问题 | GPU、驱动、CUDA、PyTorch 和 CUTLASS 版本全部入 manifest |
| B | [Unsloth #2679](https://github.com/unslothai/unsloth/issues/2679) | 视觉/统一模型路径曾忽略 `load_in_8bit=True` | 不能只检查配置值；必须核对实际 layer dtype 与显存 |

## 5. 推理量化与部署回归

| 等级 | 来源 | 本项目采用的事实 | 边界 |
|---|---|---|---|
| A/B | [Unsloth Qwen3.5 GGUF 基准](https://unsloth.ai/docs/models/qwen3.5/gguf-benchmarks) | 不同 GGUF 量化的部署质量与速度需要分别评测 | GGUF 推理基准不能预测 BnB/FP8 LoRA 的训练结果 |
| B | [Qwen3.5-9B GGUF 量化报告](https://huggingface.co/eaddario/Qwen3.5-9B-GGUF) | 提供 KLD/top-token 等量化误差方向性数据 | 社区转换与测试设置，非官方训练基准 |
| C | [LocalLLaMA Qwen3.5-9B 量化比较](https://www.reddit.com/r/LocalLLaMA/comments/1rr72lr/qwen359b_quantization_comparison/) | Q8 与不同 Q4 方法的退化并不相同，支持保留三点量化曲线 | 社区单次测试，只用于形成部署消融假设 |

## 6. 长输出、偏好优化与 Agent 后训练

| 等级 | 来源 | 用途 |
|---|---|---|
| A | [LongWriter](https://arxiv.org/abs/2408.07055) | 长输出能力与训练样本输出长度分布相关；支撑长度课程与长文专项评测 |
| A | [WritingBench](https://arxiv.org/abs/2503.05244) | 开放式写作的多维评测与写作任务覆盖参考 |
| A | [DPO](https://arxiv.org/abs/2305.18290) | 无显式奖励模型的直接偏好优化主线 |
| A | [SimPO](https://arxiv.org/abs/2405.14734) | 无参考模型、长度归一化偏好目标的消融候选 |
| A | [Length Desensitization in DPO](https://arxiv.org/abs/2409.06411) | 偏好优化中的长度偏差风险与长度控制评测依据 |
| A | [AgentTuning](https://arxiv.org/abs/2310.12823) | Agent 交互轨迹与通用指令数据混合，避免只学最终答案 |
| A | [ReAct](https://arxiv.org/abs/2210.03629) | 推理与动作交错轨迹的理论背景；ArcPen 只保留可审计的外显行动结论 |
| A | [Toolformer](https://arxiv.org/abs/2302.04761) | 工具选择与调用行为的训练背景 |

## 7. 引用与结论纪律

1. “QLoRA 论文中 INT8 与 BF16 接近”只能写成跨模型的可行性证据，不能写成“Qwen3.5 INT8 无损”。
2. “Unsloth FP8 loss 接近、节省约 8GB”属于框架自测；论文必须同时报告 ArcPen 的任务质量、显存和吞吐。
3. 官方 FP8 checkpoint 的推理性能不得推导出训练稳定性；训练版必须通过完整生命周期。
4. 任何社区模型卡、Reddit 帖和 issue 都不能单独支撑主结论，但可以定义故障注入与回归项目。
5. 精确显存是配置函数而非模型常数。报告必须包含 GPU、序列长度、有效 batch、LoRA rank/target、checkpointing、attention backend、模型实际 dtype 和峰值测量方式。

## 8. AutoDL 与 RTX 4080 Super

| 等级 | 来源 | 本项目采用的事实 |
|---|---|---|
| A | [NVIDIA RTX 4080 SUPER 规格](https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4080-family/) | 每卡 16GB、计算能力 8.9、无 NVLink |
| A | [AutoDL 学术资源加速](https://www.autodl.com/docs/network_turbo) | 终端使用 `source /etc/network_turbo`；结束后取消代理；服务不承诺稳定性 |
| A | [AutoDL 镜像文档](https://www.autodl.com/docs/image) | 保存镜像只保存实例系统盘，可在新实例选择“我的镜像”恢复 |
| A | [AutoDL 存储目录说明](https://www.autodl.com/docs/env) | 系统盘进入镜像；`/root/autodl-tmp` 数据盘不进入镜像；文件存储可跨实例共享 |
| A | [AutoDL Hugging Face 缓存说明](https://www.autodl.com/docs/huggingface) | Hugging Face 缓存应迁移到数据盘，避免撑满系统盘和污染环境镜像 |
