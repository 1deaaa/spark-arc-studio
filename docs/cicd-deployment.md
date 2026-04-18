# CI/CD 自动化部署——完整指南

本文档包含 CI/CD 自动化部署的深度技术细节。README 中仅保留概述。

---

## 1. 支持的 Git 平台

| 平台 | 配置文件 | Runner | 触发条件 |
| :--- | :--- | :--- | :--- |
| **Gitea** | `.gitea/workflows/deploy.yml` | 自建 `act_runner`（Docker 模式） | push 到 `main` 分支 |
| **GitLab** | `.gitlab-ci.yml` | 自建 GitLab Runner（Docker 模式） | push 到任意分支 |

> 💡 **关于 GitHub Actions**：Gitea Actions 的语法设计与 GitHub Actions 高度相似（`on`/`jobs`/`steps`/`secrets` 等关键字完全一致），但**并非直接兼容**，移植时需注意以下差异：
>
> - **Token 变量名**：Gitea 使用 `${{ gitea.token }}`，GitHub 使用 `${{ github.token }}`。本项目的工作流已同时读取两者并以非空者优先，因此迁移到 GitHub 后无需修改 Token 部分。
> - **托管 Runner**：GitHub 提供开箱即用的托管 Runner（`ubuntu-latest` 直接可用）；Gitea 需要在服务器上**自行部署 `act_runner`** 并以 Docker 模式运行。
> - **代码检出 Action**：标准的 `actions/checkout` 在 Gitea 上存在兼容问题。本项目绕过了这一点——检出步骤直接使用裸 `git` 命令实现，同时兼容两个平台。
> - **结论**：如果已有可用的 GitHub Actions Runner，将 `.gitea/workflows/deploy.yml` 复制到 `.github/workflows/deploy.yml` 后仅需极少量改动即可直接使用。

---

## 2. 流水线阶段

三个阶段顺序执行，任意阶段失败则终止：

```text
📥 检出代码  →  🔨 构建镜像  →  🧪 测试（预留）  →  🚀 部署  →  🧹 清理
```

1. **构建**：执行 `docker build`，利用 BuildKit 的 `--mount=type=cache` 缓存 npm/pip 包，非首次构建可大幅提速
2. **测试**：当前为预留阶段，后续将集成 `pytest` 单元测试
3. **部署**：
    - 自动创建四个持久化 Docker Volume（`sparkarc_data`、`sparkarc_userdata`、`sparkarc_shares`、`sparkarc_llm_config`），已存在则跳过
    - 若在 CI Secret 中配置了 `LLM_KEY`，自动写入容器的 `.env` 文件；未配置则启动后可通过前端设置
    - 原子替换：先删除旧容器，再以相同 Volume 启动新容器，数据零丢失
    - 启动阶段自动执行"受管文件同步"：将镜像中的 Git 受管文件覆盖回挂载目录，并清理已下线的旧受管文件；`*.db`、`.env` 等运行时数据不覆盖
4. **清理**：自动执行 `docker image prune` 清理构建过程中产生的悬空镜像

---

## 3. 配置 Gitea Runner（快速上手）

在你的服务器上，以 Docker 模式运行 `act_runner`，并将其注册到 Gitea 实例：

```bash
# 1. 获取注册 Token（Gitea 仓库 → 设置 → Actions → Runner）
# 2. 注册并启动 Runner
docker run -d \
  --name gitea-runner \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e GITEA_INSTANCE_URL=http://your-gitea-instance \
  -e GITEA_RUNNER_REGISTRATION_TOKEN=your_token \
  gitea/act_runner:latest
```

Runner 启动后，向 `main` 分支推送代码即可自动触发完整的构建和部署流程。

---

## 4. 配置 CI Secret

在你的 Git 平台仓库的 **Settings → Secrets** 中添加以下变量（可选）：

| 变量名 | 说明 |
| :--- | :--- |
| `LLM_KEY` | 大模型主密钥。配置后自动写入容器；未配置则首次启动后通过前端设置 |
