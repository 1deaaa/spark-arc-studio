# ArcPen AutoDL 环境与镜像手册

> 目标机器：AutoDL 单 vGPU 32GB；已核验为 1 个 CUDA 设备，报告名称为 NVIDIA GeForce RTX 4080 SUPER、32,760MiB
> 目标任务：9B 精度资格试验；27B INT8/FP8/Q4 生存性试验与后续可行训练

## 1. 基础镜像选择

优先选择截图中的：

```text
PyTorch 2.8.0
Python 3.12
Ubuntu 22.04
CUDA 12.8
```

该组合位于 Unsloth 当前兼容矩阵内，RTX 4080 Super 也适合 CUDA 12.8。不要选 TensorFlow、TensorRT 或社区整合镜像作为训练底座；社区镜像难以确定依赖修改和 CUDA ABI。若页面另有同等版本的 Python 3.11，可把 3.11 作为保守备选，但没有必要为了它放弃截图中已经匹配的 2.8/12.8 组合。

## 2. 第一次开机先记录硬件

```bash
nvidia-smi
nvidia-smi topo -m
python - <<'PY'
import torch
print("torch:", torch.__version__)
print("torch cuda:", torch.version.cuda)
print("cuda available:", torch.cuda.is_available())
print("gpu count:", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    print(i, p.name, p.total_memory / 1024**3, p.major, p.minor)
PY
```

预期为一张可见的 RTX 4080 SUPER、约 31.47GiB、计算能力 8.9。此实例是单 vGPU 32GB，不能将物理卡命名或常见零售规格当成容器实际可用显存；始终以 `torch.cuda.device_count()` 与 `nvidia-smi` 为准。

## 3. 开启 AutoDL 学术资源加速

终端当前会话：

```bash
source /etc/network_turbo
env | grep -i proxy
```

它主要加速 GitHub、Hugging Face 及相关静态资源。只在下载期间开启；官方不承诺稳定性，安装完成或访问普通网站异常时关闭：

```bash
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
```

Notebook 的 Python 内核不会自动继承在另一个终端后来执行的 `source`。需要在 Notebook 中下载时，按 AutoDL 官方方式把代理变量注入当前内核：

```python
import os
import subprocess

result = subprocess.run(
    'bash -c "source /etc/network_turbo && env | grep -i proxy"',
    shell=True,
    capture_output=True,
    text=True,
    check=True,
)
for line in result.stdout.splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        os.environ[key] = value
```

不要把代理地址硬编码进 Git 仓库、训练配置或永久镜像脚本；平台可能调整服务。

## 4. 把大文件缓存放到数据盘

AutoDL 镜像只保存系统盘，`/root/autodl-tmp` 是数据盘且不会进入镜像。模型、数据、输出、Hugging Face/Torch/Triton 缓存统一放数据盘：

```bash
mkdir -p /root/autodl-tmp/unsloth/{models,datasets,outputs,logs}
mkdir -p /root/autodl-tmp/cache/{huggingface,torch,triton}

cat >> /root/.bashrc <<'EOF'
export HF_HOME=/root/autodl-tmp/cache/huggingface
export HF_HUB_CACHE=/root/autodl-tmp/cache/huggingface/hub
export TORCH_HOME=/root/autodl-tmp/cache/torch
export TRITON_CACHE_DIR=/root/autodl-tmp/cache/triton
export UNSLOTH_WORKSPACE=/root/autodl-tmp/unsloth
EOF

source /root/.bashrc
```

这里追加的是普通环境变量，不包含 token。Hugging Face token 使用登录工具或临时环境变量，保存镜像前确认没有把明文密钥写进 shell 历史、`.bashrc`、Notebook 或配置文件。

## 5. 已安装的通用 Unsloth Studio

官方安装器在 `/root/.unsloth/studio/unsloth_studio` 创建了隔离环境，不污染基础镜像自带的 PyTorch 2.8.0+cu128。2026-08-22 实际验证栈为：

```text
Unsloth Studio / Core 2026.8.19
Python 3.12.3
PyTorch 2.11.0+cu130
CUDA runtime 13.0
FlashAttention 2.8.1
Transformers 5.x 兼容栈
预编译 llama.cpp 与 whisper.cpp
```

GPU 导入、FP16 CUDA 矩阵乘和 Studio 健康接口均已通过。镜像内未下载任何 Hugging Face 模型。

维护脚本：

```bash
/root/start-unsloth-studio.sh
/root/stop-unsloth-studio.sh
/root/update-unsloth-studio.sh
```

升级脚本会停止 Studio、调用官方最新版安装器、通过 AutoDL 学术代理下载 GitHub/Hugging Face 资源、让 npm 域名绕过代理，最后重新启动 Studio。不要在 Studio 隔离环境里手工升级 PyTorch、FlashAttention 或 Transformers；统一使用该脚本升级，避免 ABI 漂移。

## 6. 保存“黄金环境镜像”

建议保存，但只保存**干净、验证过的环境**：

1. 完成单 vGPU 识别、Unsloth/Transformers/PEFT/TRL 导入测试；
2. 完成一个不下载 27B 的最小前向/反向烟雾测试；
3. 确认启动、停止和一键升级脚本通过 `bash -n`；
4. 清理系统盘中的 pip/conda 临时包、错误下载和 Hugging Face 大缓存；
5. 确认模型、数据和 checkpoint 均位于 `/root/autodl-tmp`；
6. 清除 token 和敏感 shell history；
7. 关机，在“更多操作 -> 保存镜像”中保存。

建议名称：

```text
unsloth-studio-sft-rl-vgpu32-202608
```

以后租其他机器时选择“我的镜像”即可恢复系统盘环境。首次跨地区创建可能需要传输镜像；这不包含数据盘内容。

## 7. 数据和 checkpoint 不能只靠镜像

| 内容 | 推荐位置 | 是否随镜像保存 |
|---|---|---|
| Unsloth、Python 包、环境锁文件 | 系统盘 `/root/...` | 是 |
| Hugging Face 模型缓存 | `/root/autodl-tmp/cache/huggingface` | 否 |
| 数据集、manifest、评测集 | `/root/autodl-tmp/unsloth/datasets` | 否 |
| adapter、checkpoint、日志 | `/root/autodl-tmp/unsloth/outputs` | 否 |
| 长期重要产物 | AutoDL 文件存储、对象存储或本地至少一份 | 独立备份 |

同地区换实例可使用跨实例拷贝数据盘；跨地区使用 AutoDL 文件存储、公网网盘或对象存储。系统盘和数据盘都是本地盘，不能把实例持续存在当成备份。

## 8. 单 vGPU 32GB 的训练边界

- 容器只有一个约 31.47GiB 的 CUDA 设备，不启用 DDP、模型分片或 CPU offload。
- 27B INT8/FP8 可以先做正式资格试验，但不能据此假设 8K/16K 一定放得下。
- 记录实际 tokens/s、峰值显存、可见 GPU 数和设备名称；vGPU 显存配额是唯一有效硬件约束。
- 第一次只跑 2K、batch 1、rank 16、3 step，不直接下载数据后开始全量训练。
- 峰值显存不能留出至少 2GiB 安全余量、出现 CPU offload 或不能保存/恢复/合并，即判 INT8/FP8 不适合作为正式 27B 路线。
- 27B INT8/FP8 先走完整资格试验；若显存余量或生命周期不通过，再使用 Q4 QLoRA，并与 9B INT8/BF16 锚点比较质量。
