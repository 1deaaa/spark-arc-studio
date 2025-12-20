# 前端架构优化记录 (2025-12-21)

本文档记录了 SparkArc 前端项目的系统级重构，旨在提升代码可维护性、UI 一致性及系统性能。

## 1. 核心架构重构

### 1.1 模块化 API 服务 (`src/services/`)
- **现状**：原有 `api.js` 为 400+ 行的单体文件，逻辑耦合严重。
- **改进**：拆分为五个功能明确的子模块：
  - `apiClient.js`: 基础 Fetch 封装与 SWR 缓存逻辑。
  - `authService.js`: 登录、注册、用户信息管理。
  - `projectService.js`: 项目创建、删除、列表获取。
  - `storyService.js`: 剧本编辑、文件操作、历史记录、蓝图管理。
  - `aiService.js`: AI 代理接口（Muse, Outline, Style, Bridge）。
- **兼容性**：通过 `api.js` 聚合导出所有子模块，现有组件无需修改 `import` 路径即可直接运行。

### 1.2 组件职责拆分 (`src/components/dlg-editor/`)
- **改进**：从 `DialogueTree.vue` 中提取出 `DialogueNode.vue`。
- **收益**：
  - 消除了根节点与子节点之间 80% 的重复模板逻辑。
  - 实现了更清晰的递归渲染，便于未来对“对话节点”进行功能扩展。
  - 提升了代码可读性，将复杂的拖拽参数和样式逻辑封装在子组件内部。

---

## 2. 视觉与主题系统优化

### 2.1 唯一事实来源 (SSoT) 颜色系统
- **设计令牌 (`src/styles/tokens.js`)**：
  - 将 **星空蓝 (Dark)** 和 **鼠尾草绿 (Light)** 定位为核心主色。
  - 引入衍生算法，自动生成 Hover 态、发光色 (Glow) 和 容器背景色 (Container)。
- **动态同步 (`src/styles/themeConfig.js`)**：
  - 通过 `watchEffect` 实时将 JS 定义的色值同步到 CSS 变量 (`--spark-primary` 等)。
  - **收益**：修改 `tokens.js` 即可实现全站（组件库 + 自定义 CSS）的配色同步。

---

## 3. 性能与健壮性优化

### 3.1 布局逻辑解耦 (`src/hooks/useResizer.js`)
- **改进**：将 `MainView.vue` 中的面板拖拽缩放逻辑封装为 Vue Composable。
- **收益**：
  - 移除了 `MainView.vue` 中所有脆弱的 `querySelector` 命令式 DOM 操作。
  - 实现了响应式的宽度绑定（`:style="{ width: ... }"`）。
  - 面板尺寸持久化 (LocalStorage) 逻辑更加稳健。

### 3.2 Vite 构建优化 (`vite.config.js`)
- **配置**：引入 `manualChunks` 分包策略。
- **收益**：
  - 将 `naive-ui`、`vicons` 等大型库从主包分离。
  - 极大缩减了主 bundle 体积，提升首屏加载速度并优化浏览器缓存命中率。

---

## 4. 后续维护建议
1. **API 调用**：新功能开发应直接从具体 Service（如 `authService`）导入，逐步减少对 `api.js` 中转站的依赖。
2. **样式使用**：优先使用 CSS 变量（如 `var(--spark-primary)`），这些变量已与主题引擎自动绑定。
3. **状态管理**：复杂的 UI 状态同步建议继续向 Pinia 迁移，减少全局事件总线 (`mitt`) 的使用。

---
*SparkArc Team - 2025*
