# ArcPen AutoDL 环境与镜像手册

> 目标机器：双 NVIDIA GeForce RTX 4080 Super，每卡 16GB  
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

预期为两张 4080 Super、约 16GiB/卡、计算能力 8.9。若只识别一张卡，停止安装和训练，先检查实例租用数量。

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
mkdir -p /root/autodl-tmp/arcpen/{models,data,outputs,logs}
mkdir -p /root/autodl-tmp/cache/{huggingface,torch,triton}

cat >> /root/.bashrc <<'EOF'
export HF_HOME=/root/autodl-tmp/cache/huggingface
export HF_HUB_CACHE=/root/autodl-tmp/cache/huggingface/hub
export TORCH_HOME=/root/autodl-tmp/cache/torch
export TRITON_CACHE_DIR=/root/autodl-tmp/cache/triton
export ARCPEN_ROOT=/root/autodl-tmp/arcpen
EOF

source /root/.bashrc
```

这里追加的是普通环境变量，不包含 token。Hugging Face token 使用登录工具或临时环境变量，保存镜像前确认没有把明文密钥写进 shell 历史、`.bashrc`、Notebook 或配置文件。

## 5. 安装最新版 Unsloth

先使用官方检测脚本确认安装变体。当前基础镜像应对应 `cu128-torch280`，但以脚本实际输出为准：

```bash
python - <<'PY'
import re
import torch
from packaging.version import Version as V

v = V(re.match(r"[0-9.]{3,}", torch.__version__).group(0))
cuda = str(torch.version.cuda)
print("torch=", v, "cuda=", cuda)
assert cuda == "12.8", (v, cuda)
assert V("2.8.0") <= v < V("2.8.9"), v
print("Unsloth variant: cu128-torch280")
PY
```

开启学术加速后安装，并记录精确版本：

```bash
source /etc/network_turbo
python -m pip install --upgrade pip
python -m pip install --no-deps git+https://github.com/unslothai/unsloth-zoo.git
python -m pip install "unsloth[cu128-torch280] @ git+https://github.com/unslothai/unsloth.git" --no-build-isolation
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY

python -m pip freeze > /root/arcpen-environment.lock.txt
```

不要在同一环境中随意再次安装另一套 PyTorch、CUDA wheel 或 vLLM。需要 vLLM 时明确选择 `cu128` backend，并在安装后重新运行导入与 GPU 烟雾测试。

## 6. 保存“黄金环境镜像”

建议保存，但只保存**干净、验证过的环境**：

1. 完成双卡识别、Unsloth/Transformers/PEFT/TRL 导入测试；
2. 完成一个不下载 27B 的最小前向/反向烟雾测试；
3. 保存 `/root/arcpen-environment.lock.txt` 和环境检查脚本；
4. 清理系统盘中的 pip/conda 临时包、错误下载和 Hugging Face 大缓存；
5. 确认模型、数据和 checkpoint 均位于 `/root/autodl-tmp`；
6. 清除 token 和敏感 shell history；
7. 关机，在“更多操作 -> 保存镜像”中保存。

建议名称：

```text
arcpen-unsloth-torch280-cu128-py312-202608
```

以后租其他机器时选择“我的镜像”即可恢复系统盘环境。首次跨地区创建可能需要传输镜像；这不包含数据盘内容。

## 7. 数据和 checkpoint 不能只靠镜像

| 内容 | 推荐位置 | 是否随镜像保存 |
|---|---|---|
| Unsloth、Python 包、环境锁文件 | 系统盘 `/root/...` | 是 |
| Hugging Face 模型缓存 | `/root/autodl-tmp/cache/huggingface` | 否 |
| 数据集、manifest、评测集 | `/root/autodl-tmp/arcpen/data` | 否 |
| adapter、checkpoint、日志 | `/root/autodl-tmp/arcpen/outputs` | 否 |
| 长期重要产物 | AutoDL 文件存储、对象存储或本地至少一份 | 独立备份 |

同地区换实例可使用跨实例拷贝数据盘；跨地区使用 AutoDL 文件存储、公网网盘或对象存储。系统盘和数据盘都是本地盘，不能把实例持续存在当成备份。

## 8. 双卡训练的硬约束

- 双 4080 Super 是两个独立 16GB 地址空间，不是单张 32GB。
- 27B INT8/FP8 必须采用模型分片；普通 DDP 会在每张卡复制完整模型并直接 OOM。
- 4080 Super 没有 NVLink，必须记录 `nvidia-smi topo -m`、跨卡通信和实际 tokens/s。
- 第一次只跑 2K、batch 1、rank 16、3 step，不直接下载数据后开始全量训练。
- 任一卡没有至少 1GiB 安全余量、出现 CPU offload 或不能保存/恢复/合并，即判 INT8/FP8 不适合作为正式 27B 路线。
- 27B Q4 QLoRA 是双 16GB 更现实的训练候选，但仍必须与 9B INT8/BF16 锚点比较质量，不能因“能跑”就宣称更优。
