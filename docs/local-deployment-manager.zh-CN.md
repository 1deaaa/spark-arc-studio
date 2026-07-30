# Launcher 本地部署管理器

## 目标

SparkArc 保留两条互不混淆的使用路径：

1. 源码部署：开发者和自部署者手动管理 Git、Node 与分支。
2. Launcher 受管部署：Launcher 在 `~/.sparkarc/sparkarc-server` 管理唯一的 `main` 工作树，用户不需要安装系统 Git 或 Node。

Launcher 不是第二套业务客户端。它只负责安装、启动、更新检查、日志和低频壳更新提示；业务页面仍由本地后端托管。

## 唯一收口

原生部署逻辑统一位于：

`client/src-tauri/src/deployment/mod.rs`

Vue Launcher 页面只读取状态并调用 Tauri 命令，不直接执行 Git、下载或文件切换。`start.bat`、`start.sh` 只负责在源码已就绪后构建前端并启动服务。

Launcher 的本地后端目录固定为 `~/.sparkarc/sparkarc-server`。

## 工作树所有权

Launcher 首次拉取源码后，在根目录写入 `.sparkarc-managed.json`：

- 固定仓库为 `1deaaa/spark-arc-studio`。
- 固定更新通道为 `main`。
- 记录当前提交与写入时间。

只有带有该标记、且远端仓库身份匹配的目录允许自动更新。用户手动 clone 的 `dev`、其他分支或任意本地改造目录不会被 Launcher 覆盖。

旧版 Launcher 已创建的 `~/.sparkarc/sparkarc-server` 会在确认 `origin` 指向官方仓库后迁移到 APP 数据目录；无法确认身份时保持只启动、不接管。

## 源码更新

受管源码更新使用内嵌 `git2` 的 HTTPS 实现，不调用系统 `git`：

1. `check_local_update` 只 fetch `refs/heads/main`，比较本地和远端 SHA，不改工作树。
2. Launcher 先停止自己登记的受管后端，并确认 6688 端口已释放，`apply_local_update` 才会执行。
3. 更新前拒绝未声明的源码改动；`server/data`、`server/_userdata`、`server/shares_data`、运行时缓存和前端产物属于受保护路径。
4. 更新失败时，Git 检出会回到旧提交并恢复已备份的受保护文件。

当前版本不在运行中的服务上执行代码切换。用户通过 Launcher 选择“更新并启动”后，控制面依次执行“停止受管服务 → 应用提交 → 启动后端”，避免前端、后端和磁盘文件处于混合版本。若旧版服务没有 Launcher 进程记录但仍占用 6688，系统会拒绝猜测和强杀，要求用户先手动停止。

## 网络与可信来源

Git 源按顺序尝试：

1. `SPARKARC_GIT_REMOTE` 显式覆盖值。
2. 中国大陆网络优先 Gitee 公开镜像，再回退到 GitHub 官方 HTTPS 仓库。
3. 非中国大陆或地区无法确认时优先 GitHub 官方仓库，并保留 Gitee 作为回退。

源码克隆与更新不再使用公共 GitHub 代理，避免大体积 pack 传输卡死。Gitee 镜像地址由根目录 `sparkarc.json` 统一声明，Launcher、Python 网络探测和 PowerShell 启动链路共同读取。

Release 检查同样按出口地区选择来源：中国大陆优先请求 `sparkarc.json` 声明的 Gitee Release API，再回退到 GitHub 代理和官方 API；非中国大陆或地区未知时优先 GitHub 官方 API，再尝试代理与 Gitee。`SPARKARC_GITHUB_RELEASE_API` 仍可覆盖并优先尝试兼容的 GitHub API。所有 API 均不可用时，会回退到 GitHub 标准 `/releases/latest` 重定向页；成功使用代理时，返回给用户的下载页也会使用同一前缀。

Release 成功结果会在本机缓存 6 小时，避免每次启动都重复消耗平台 API 配额。它只用于低频 Launcher 壳更新提示，不是业务源码更新清单；探测策略升级时旧缓存会自动失效。

## 受管 Node

Launcher 使用固定的 Node.js `24.16.0`：

- 下载到 `~/.sparkarc/tools/node/<版本>/<平台>`。
- 优先 Node 官方源，失败后尝试 npmmirror；可通过 `SPARKARC_NODE_DIST_MIRROR` 覆盖。
- Windows x64/arm64、macOS Intel/Apple Silicon、Linux x64/arm64 都使用官方 SHA-256 固定校验。
- 启动受管工作树时，仅向子进程临时前置该 Node 的 PATH，不修改用户环境变量。

前端构建统一通过 `client/build-frontend.mjs` 执行 `npm ci` 和 `npm run build`。Windows 与 Unix 不再维护不同的构建状态机。

## Launcher 壳更新

Launcher 自身的更新与 `main` 源码更新分离：

- 每次 Launcher 启动可调用 `check_launcher_update`。
- 该命令读取 GitHub 最新稳定 Release 的 tag 与页面地址，并保留 API 限流时的标准跳转页回退。
- 首期仅提示并打开对应 Release 下载页。
- 后续接入 Tauri Updater 时，仍复用 GitHub Release，不增加自定义远端 manifest。

壳版本不会参与普通业务前后端的版本锁定。只有未来部署协议发生不兼容变化时，才应引入最低 Launcher 能力限制。

## 后续增强

当前实现先保证“受管 main + 私有 Git/Node + 显式更新”的单一主链。后续可在同一模块中继续补充：

1. staging 工作树中的完整依赖与前端预构建。
2. 启动失败后的进程树停止、数据库备份与自动回滚。
3. 业务前端中的更新通知和安全的本地 Launcher 控制通道。
4. 已签名 Tauri 自更新安装包。
