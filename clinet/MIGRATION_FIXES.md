# Naive UI 迁移修复总结

## 已完成的修复

### 1. ✅ 亮色模式下头部按钮可见性优化
- **问题**: 亮色模式下，头部菜单栏按钮边框和文字颜色太浅，可见性差
- **解决方案**: 
  - 移除了覆盖 Naive UI 默认样式的旧 CSS 规则
  - Naive UI 的按钮组件会自动适配亮色/暗色主题
  - 只保留了禁用 transform 和 box-shadow 的特定样式

### 2. ✅ 对话树节点边框增强
- **问题**: 未选中的对话树节点没有边框，可见性不够
- **解决方案**:
  - 给所有节点添加了 `box-shadow: 0 0 0 1px rgba(128, 128, 128, 0.2)` 灰色细边框
  - 选中状态边框从蓝色 0.5 透明度提升到 0.8，更加明显
  - 添加了 hover 状态边框效果

### 3. ✅ 使用 Naive UI 原生确认框
- **状态**: 已经在使用 Naive UI 的 `n-popconfirm` 组件
- **位置**:
  - 项目删除: `ProjectSelector.vue` 使用 `n-popconfirm`
  - 角色删除: `LorebookEditor.vue` 使用 `n-popconfirm`
  - 文件/文件夹删除: `fileStore.js` 使用 bus 事件（连接到 `ContextPrompt.vue`）

### 4. ✅ 修复新建文件/文件夹功能
- **问题**: MainView.vue 中有重复的 ModalHost 和 ContextPrompt 组件，导致事件监听混乱
- **解决方案**:
  - 移除了 MainView.vue 中重复的 `<ModalHost />` 和 `<ContextPrompt />` 组件
  - 统一使用 App.vue 中的全局实例
  - 确保 bus 事件正确路由到全局组件

### 5. ✅ 修复右侧面板滚动问题
- **问题**: 右侧面板内容超出时没有出现滚动条，底部按钮不可见
- **解决方案**:
  - 移除了 `.panel` 的 `overflow: hidden`
  - 为每个面板的子元素（除了 h2 标题）设置独立的滚动
  - 添加 `flex: 1` 和 `min-height: 0` 确保正确的 flex 布局
  - 左侧、中间、右侧面板现在都能正确滚动

### 6. ✅ 深色模式优化
- **文件树**: 简化了深色模式样式，依赖 Naive UI 自动适配
- **对话树**: 
  - 增强了对话内容在深色模式下的可见性（opacity: 1）
  - 优化了节点预览文本的透明度
- **表单元素**: 
  - 使用精确的 CSS 选择器排除 Naive UI 组件内的原生元素
  - 使用 `:is()` 伪类选择器避免样式冲突
  - 只对非 Naive UI 的原生 HTML 表单元素应用深色样式

### 7. ✅ CSS 清理
删除了大量迁移后遗留的废弃样式：
- 旧的 `.badge` 样式（已用 `n-tag` 替代）
- 旧的 `.tree-node` 样式（已迁移到组件 scoped 样式）
- 旧的 `.context-menu` 样式（已用 `n-dropdown` 替代）
- 旧的 `.file-item` 样式（已迁移到组件 scoped 样式）
- 简化了拖拽相关样式（`.sortable-*`）

## 文件变更列表

### 修改的文件
1. `clinet/src/style.css` - 主要样式文件，清理和优化
2. `clinet/src/App.vue` - 优化主题配置
3. `clinet/src/MainView.vue` - 移除重复组件
4. `clinet/src/components/file-explorer/FileTree.vue` - 迁移到 Naive UI Dropdown
5. `clinet/src/components/file-explorer/FileItem.vue` - 迁移到 Naive UI Dropdown
6. `clinet/src/components/dlg-editor/DialogueTree.vue` - 迁移到 Naive UI Card/Tag/Empty

## 技术要点

### Naive UI 组件使用
- **NDropdown**: 替代原生右键菜单，支持自动主题切换
- **NCard**: 对话树节点，自动适配深浅色
- **NTag**: 替代自定义 badge，多种预设类型
- **NEmpty**: 空状态展示，更友好的用户体验
- **NEllipsis**: 文本省略，自动处理溢出

### CSS 选择器优化
```css
/* 错误示例 - 会影响 Naive UI 内部元素 */
body.dark-mode input[type="text"] { }

/* 正确示例 - 排除 Naive UI 组件 */
body.dark-mode :is(input[type="text"]):not(:is(.n-input *, .n-form *, [class*="n-"] *)) { }
```

### Flex 布局滚动
```css
/* 父容器 */
.panel {
    display: flex;
    flex-direction: column;
    min-height: 0;
}

/* 可滚动子元素 */
.panel > *:not(h2) {
    overflow-y: auto;
    flex: 1;
    min-height: 0;
}
```

## 测试建议

### 功能测试
- [ ] 新建文件/文件夹是否弹出输入框
- [ ] 文件树右键菜单是否正常显示和工作
- [ ] 对话树节点拖拽是否正常
- [ ] 右侧面板滚动是否流畅
- [ ] 各种删除确认框是否正常

### 主题测试
- [ ] 切换系统深浅色模式，所有组件是否正确响应
- [ ] 亮色模式下按钮是否清晰可见
- [ ] 暗色模式下对话内容是否清晰
- [ ] 输入框在两种模式下是否正常显示（无奇怪色块）

### 兼容性测试
- [ ] Windows 系统主题切换
- [ ] 不同屏幕分辨率下的布局
- [ ] 拖拽调整面板宽度后的滚动表现

## 后续优化建议

1. **完全移除原生 context menu**: 目前仍有一些地方可能使用原生右键菜单，可以全部替换为 Naive UI 的 Dropdown
2. **统一事件系统**: 考虑使用 Naive UI 的 useDialog 和 useMessage 替代自定义的 bus 事件系统
3. **性能优化**: 对话树在节点很多时可以考虑虚拟滚动
4. **主题定制**: 可以进一步定制 Naive UI 的主题变量以完全匹配设计系统

## 注意事项

- 所有 Naive UI 组件会自动响应 `darkTheme` 的切换，无需手动添加深色样式
- 避免使用 `!important` 覆盖 Naive UI 的样式，优先使用 `themeOverrides`
- 保持 scoped 样式与全局样式的清晰边界，避免样式冲突
