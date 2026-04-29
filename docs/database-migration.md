# 数据库自动迁移——完整指南

本文档包含数据库自动迁移系统的深度技术细节。README 中仅保留概述和救命方法。

---

## 1. 自动迁移特性

1. **多数据库分支**：`users.db` 与 `llm_config.db` 采用独立 `version_locations`，互不干扰
2. **启动自动升级**：启动时使用 Alembic API 直接升级
3. **临时库生成迁移**：`gen_migration.py` 先用已提交迁移链构造临时 head DB，再与当前 Models 对比，避免开发机真实 DB 污染迁移结果
4. **自动跳过**：启动时先读取 `alembic_version` 与脚本 head，已是最新且无缺失结构时直接跳过
5. **最早阶段执行**：迁移在 `lifespan` 最前面完成，避免业务初始化占用 SQLite 锁
6. **智能重命名检测**：当开发者在代码中重命名数据库字段时，迁移工具会自动识别并询问确认，避免了传统工具"先删除再新增"导致的数据丢失风险
7. **危险操作拦截**：任何涉及 `DROP COLUMN`（删除列）或 `DROP TABLE`（删除表）的修改，在生成迁移脚本阶段都会被强制拦截并要求开发者交互确认
8. **孤儿版本自愈**：当底层迁移链被上游仓库重置打断时，启动期自愈机制会自动补缺失表/列并 stamp 到 head；默认保留额外表/列，不做破坏性删除
9. **head 漂移保护**：如果版本号已是 head 但 DB 缺少当前模型字段，启动期默认报错，防止悄悄修库吞掉应提交给下游的 migration

---

## 2. 开发者工作流（改表 → 迁移 → 审核 → 发布）

1. **修改模型**（`server/core/models.py` 或 `server/llm/agen_matchbox/models.py`）
2. **生成迁移**：

    ```bash
    cd server
    python gen_migration.py
    ```

3. **处理冲突**：如有重命名/删除等危险操作，按提示确认或取消；不要手写迁移脚本
4. **提交迁移**：将生成的迁移文件提交到仓库
5. **用户拉取代码**：无需手动迁移，启动服务会自动执行升级

> 💡 **开发者注意**：
>
> - 🚫警告：禁止手写迁移文件和修改现有迁移文件，这会造成冲突
> - 修改 `core/models.py` (Users DB) 后，运行 `python gen_migration.py users "说明"`
> - 修改 `llm/agen_matchbox/models.py` (LLM DB) 后，运行 `python gen_migration.py llm "说明"`
> - 如果不指定数据库名，默认会对所有数据库生成迁移：`python gen_migration.py "说明"`
> - 生成脚本不会读取真实运行库作为 autogenerate 基准；如果临时库升级后仍与 Models 不一致，脚本会失败并指出缺失/多余结构。

### 2.1 救急开关

- `SPARKARC_AUTO_MIGRATE_REPAIR_HEAD_DRIFT=1`：当 `alembic_version` 已是 head 但 DB 缺表/缺列时，允许启动期按 Models 补缺失对象。默认关闭，避免开发机悄悄修库后吞掉 migration。
- `SPARKARC_AUTO_MIGRATE_ALLOW_DROPS=1`：孤儿版本自愈时允许删除 Models 未定义的额外列/表。默认关闭；除非已备份数据库且确认这些结构无用，否则不要开启。
- `SPARKARC_ALEMBIC_USERS_DB` / `SPARKARC_ALEMBIC_LLM_DB`：覆盖 Alembic 目标 DB 路径。未设置时，LLM DB 会跟随 `AGENT_MATCHBOX_HOME`，保证迁移目标和运行时 manager 使用同一个文件。

---

## 3. 将自动迁移基础设施接入你的应用

如果你想将这套自动数据库迁移逻辑（自动升级、多库支持、重命名检测）复用到其他 FastAPI 项目，请务必改清楚以下"必改项"，做到开箱即用：

### 3.1 复制核心文件

- `server/alembic/` (目录)：包含环境配置 `env.py` 和脚本模板
- `server/alembic.ini`：配置文件
- `server/gen_migration.py`：生成迁移的 CLI 工具
- `server/core/auto_migrate.py`：负责运行时自动升级的逻辑

### 3.2 必改项清单（迁移到新项目一定要改）

- **数据库路径**：
    - `server/core/migration_specs.py` 中的 `DB_SPECS` / `get_db_path`
- **Metadata 入口**：
    - `server/core/migration_specs.py` 中 `load_metadata`
- **多库分支命名**：
    - `server/alembic.ini` 中的 `[users]` / `[llm]` 段落名称
    - `server/core/migration_specs.py` 中的 `DB_SPECS`
- **自定义类型渲染**：
    - 如果你有自定义类型（如 `SqliteJSONB`），必须在 `env.py` 里加 `render_item` 规则
    - `render_as_batch_mode` 是为 SQLite 设计，Postgres/MySQL 应关闭
- **业务启动入口**：
    - `app.py` 中 `lifespan` 里调用 `run_auto_migrations()` 的位置要靠前

### 3.3 配置多数据库（可选）

- 修改 `server/core/migration_specs.py` 中的 `DB_SPECS`、`get_db_path` 和 `load_metadata`
- 在 `server/alembic.ini` 中补充对应 section 与 `version_locations`

### 3.4 接入应用生命周期

在你的 `app.py` 或 `main.py` 的 lifespan 中调用 `run_auto_migrations`：

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from core.auto_migrate import run_auto_migrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 启动时自动迁移
    try:
        run_auto_migrations()
    except Exception as e:
        print(f"Migration failed: {e}")
        raise e
    
    yield
    
app = FastAPI(lifespan=lifespan)
```

---

## 4. 清理迁移历史（⚠️ 高风险操作）

⚠️ 警告：如果你需要用 Git 在多个地方同步仓库，那么**禁止执行清理历史**。这会导致拉取者出现数据库版本错误。除非你确定你的操作只涉及最简单的增删。

⚠️ 自愈机制只是兜底，处理掉简单的增删。如果清理掉了涉及重命名和修改字段类型或约束，而下游拉取者又没有来得及同步之前的迁移历史，会导致拉取者出现错误！

⚠️ 只有你在本地独自开发的时候才能使用这个脚本！

⚠️ 新版 `gen_migration.py` 已经不依赖真实运行库生成迁移，因此一般不需要通过清理历史来“修正 autogenerate”。清历史只适合私有开发阶段压缩历史；公开分支应只追加迁移。

```bash
cd server
python clear_migration.py --yes
```

该脚本会：

1. 先升级到最新 head
2. 备份/删除旧迁移
3. 使用空数据库生成新的基线迁移
4. 将真实数据库 stamp 到新 head
5. 再用临时库隔离模式验证新迁移链能从零升级到当前 Models
