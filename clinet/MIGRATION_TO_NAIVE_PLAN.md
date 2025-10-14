# 迁移到 Naive UI 组件计划

## 🎯 目标
用 Naive UI 原生组件替换当前的原生 HTML/CSS 实现，实现：
1. ✅ 自动深浅色适配（删除所有 `body.dark-mode` CSS）
2. ✅ 更强大的功能（搜索、过滤、虚拟滚动）
3. ✅ 更少的代码量
4. ✅ 更好的用户体验

---

## 📦 组件替换对照表

| 当前实现 | 替换为 Naive UI 组件 | 优势 |
|---------|---------------------|------|
| **文件树** (FileTree.vue + FileItem.vue) | `NTree` | • 内置展开/折叠<br>• 支持拖拽 (draggable)<br>• 自动深浅色<br>• 图标、右键菜单<br>• 内置编辑功能 |
| **场景列表** (SceneList.vue) | `NList` + `NListItem` | • 自动深浅色<br>• 支持虚拟滚动<br>• 内置选中状态 |
| **对话树** (DialogueTree.vue) | `NTree` (自定义渲染) | • 层级结构展示<br>• 可自定义节点<br>• 自动深浅色<br>• 支持搜索、过滤 |

---

## 🔄 详细迁移方案

### 1️⃣ 文件树 (FileTree.vue) → NTree

#### 当前实现问题：
- 手动实现展开/折叠逻辑
- 拖拽依赖 `vuedraggable`
- 需要大量 CSS 适配深浅色
- 右键菜单需要手动定位

#### Naive UI 方案：

```vue
<template>
  <n-tree
    :data="treeData"
    :node-props="nodeProps"
    :draggable="true"
    :selectable="true"
    :show-irrelevant-nodes="false"
    :render-prefix="renderPrefix"
    :render-suffix="renderSuffix"
    @update:selected-keys="handleSelect"
    @drop="handleDrop"
  />
</template>

<script setup>
import { ref, computed } from 'vue';
import { NTree, NIcon, NDropdown } from 'naive-ui';
import { FolderOutline, DocumentTextOutline } from '@vicons/ionicons5';
import { useFileStore } from '@/components/stores/fileStore';

const fileStore = useFileStore();

// 转换文件树数据为 NTree 格式
const treeData = computed(() => {
  return convertToTreeData(fileStore.fileTree);
});

function convertToTreeData(files) {
  return files.map(file => ({
    key: file.path,
    label: file.name,
    isLeaf: file.type === 'story',
    children: file.children ? convertToTreeData(file.children) : undefined,
    type: file.type
  }));
}

// 自定义图标前缀
const renderPrefix = ({ option }) => {
  const icon = option.type === 'folder' ? FolderOutline : DocumentTextOutline;
  return h(NIcon, null, { default: () => h(icon) });
};

// 右键菜单
const contextMenuOptions = [
  { label: '重命名', key: 'rename' },
  { label: '删除', key: 'delete', props: { style: { color: 'red' } } }
];

const nodeProps = ({ option }) => {
  return {
    onContextmenu(e) {
      e.preventDefault();
      // 显示右键菜单
    }
  };
};

// 拖拽处理
function handleDrop({ node, dragNode, dropPosition }) {
  fileStore.moveFile(dragNode.key, node.key, dropPosition);
}

// 选中处理
function handleSelect(keys) {
  if (keys.length > 0) {
    fileStore.openFile(keys[0]);
  }
}
</script>
```

**代码减少量**: 约 200 行 → 80 行

---

### 2️⃣ 场景列表 (SceneList.vue) → NList

#### 当前实现问题：
- 手动管理选中状态
- 手动处理 hover 样式
- 需要 CSS 适配深浅色

#### Naive UI 方案：

```vue
<template>
  <n-list hoverable clickable>
    <n-list-item
      v-for="scene in scenes"
      :key="scene.id"
      :class="{ 'selected': scene.id === selectedSceneId }"
      @click="selectScene(scene.id)"
    >
      <template #prefix>
        <n-icon :component="DocumentTextOutline" />
      </template>
      <n-thing :title="scene.name">
        <template #description>
          场景容量: {{ scene.cap }} | 进度: {{ scene.pgrs }}
        </template>
      </n-thing>
    </n-list-item>
  </n-list>
</template>

<script setup>
import { NList, NListItem, NThing, NIcon } from 'naive-ui';
import { DocumentTextOutline } from '@vicons/ionicons5';
import { useSceneStore } from '@/components/stores/sceneStore';

const sceneStore = useSceneStore();
const scenes = computed(() => sceneStore.scenes);
const selectedSceneId = computed(() => sceneStore.currentSceneId);

function selectScene(id) {
  sceneStore.selectScene(id);
}
</script>

<style scoped>
.n-list-item.selected {
  background-color: var(--n-color-target);
}
</style>
```

**代码减少量**: 约 150 行 → 50 行

---

### 3️⃣ 对话树 (DialogueTree.vue) → NTree (自定义渲染)

#### 当前实现问题：
- 手动实现树形结构
- 手动管理展开/折叠
- 大量 CSS 代码
- 深浅色适配复杂

#### Naive UI 方案：

```vue
<template>
  <n-tree
    :data="dialogueTreeData"
    :selectable="true"
    :render-label="renderLabel"
    :render-prefix="renderPrefix"
    :node-props="nodeProps"
    @update:selected-keys="handleSelect"
  />
</template>

<script setup>
import { h, computed } from 'vue';
import { NTree, NTag, NText, NIcon } from 'naive-ui';
import { ChatbubbleOutline, GitBranchOutline } from '@vicons/ionicons5';
import { useSceneStore } from '@/components/stores/sceneStore';

const sceneStore = useSceneStore();

// 转换对话数据为树形结构
const dialogueTreeData = computed(() => {
  const scene = sceneStore.currentScene;
  if (!scene) return [];
  
  return buildDialogueTree(scene.dialogues);
});

function buildDialogueTree(dialogues) {
  return dialogues.map(dlg => ({
    key: dlg.id,
    label: dlg.txt,
    type: dlg.type, // 'dialogue' or 'option'
    character: dlg.chr,
    children: dlg.next ? buildDialogueTree(dlg.next) : undefined
  }));
}

// 自定义节点渲染
const renderLabel = ({ option }) => {
  return h('div', { class: 'dialogue-node-content' }, [
    h(NTag, {
      size: 'small',
      type: option.type === 'dialogue' ? 'info' : 'success'
    }, { default: () => option.character || '旁白' }),
    h(NText, { style: { marginLeft: '8px' } }, { default: () => option.label })
  ]);
};

// 自定义图标
const renderPrefix = ({ option }) => {
  const icon = option.type === 'dialogue' ? ChatbubbleOutline : GitBranchOutline;
  return h(NIcon, null, { default: () => h(icon) });
};

// 节点右键菜单
const nodeProps = ({ option }) => {
  return {
    onClick() {
      sceneStore.selectDialogue(option.key);
    },
    onContextmenu(e) {
      e.preventDefault();
      // 显示编辑/删除菜单
    }
  };
};
</script>
```

**代码减少量**: 约 300 行 → 100 行

---

## 🗑️ 可以删除的代码

### CSS (style.css)
删除以下部分（约 **400 行**）：
```css
/* 删除 */
body.dark-mode .file-item { ... }
body.dark-mode .file-item:hover { ... }
body.dark-mode .scene-item { ... }
body.dark-mode .dialogue-node { ... }
body.dark-mode .tree-node { ... }
/* ... 所有 body.dark-mode 相关样式 */

/* 删除 */
.file-tree { ... }
.file-item { ... }
.file-item:hover { ... }
.scene-list { ... }
.scene-item { ... }
.dialogue-tree { ... }
.tree-node { ... }
/* ... 所有原生树形组件样式 */
```

### JavaScript
- `vuedraggable` 依赖（可选，如果其他地方不用）
- 手动管理的展开/折叠状态
- 手动管理的选中状态
- 复杂的拖拽逻辑

---

## 📊 迁移收益

| 项目 | 迁移前 | 迁移后 | 减少 |
|-----|-------|-------|------|
| CSS 代码 | ~600 行 | ~50 行 | **-92%** |
| JS 代码 | ~650 行 | ~230 行 | **-65%** |
| 深浅色适配 | 手动写 400 行 | **自动** | **-100%** |
| 依赖包 | vuedraggable | Naive UI | 已有 |
| 功能完整性 | 基础 | **增强** | ⬆️ |

---

## 🚀 迁移步骤

### 阶段 1: 文件树迁移 (1-2 小时)
1. ✅ 安装依赖（已完成，Naive UI 已安装）
2. 📝 重写 `FileTree.vue` 使用 `NTree`
3. 📝 重写 `FileItem.vue` 或删除（合并到 FileTree）
4. 🗑️ 删除相关 CSS
5. ✅ 测试拖拽、右键菜单、编辑功能

### 阶段 2: 场景列表迁移 (30 分钟)
1. 📝 重写 `SceneList.vue` 使用 `NList`
2. 🗑️ 删除相关 CSS
3. ✅ 测试选中、点击功能

### 阶段 3: 对话树迁移 (1-2 小时)
1. 📝 重写 `DialogueTree.vue` 使用 `NTree`
2. 📝 自定义节点渲染（标签、图标）
3. 🗑️ 删除相关 CSS
4. ✅ 测试层级展示、选中、编辑

### 阶段 4: 清理 (30 分钟)
1. 🗑️ 删除所有 `body.dark-mode` CSS（约 400 行）
2. 🗑️ 删除 `App.vue` 中的 `syncBodyClass` 逻辑
3. 🗑️ 删除 `vuedraggable` 依赖（如果不需要）
4. ✅ 全局测试深浅色切换

---

## 💡 关键优势

### 1. 自动深浅色适配
```vue
<!-- 不需要任何额外代码！ -->
<n-tree :data="data" />
```
Naive UI 的所有组件都会自动跟随 `darkTheme`，无需手动写 CSS。

### 2. 更强大的功能
- **NTree** 支持：
  - 虚拟滚动（大数据性能优化）
  - 内置搜索/过滤
  - 键盘导航
  - 拖拽排序
  - 异步加载子节点
  
### 3. 统一的设计语言
所有组件风格一致，用户体验更好。

### 4. 更少的维护成本
- 不需要维护大量自定义 CSS
- 升级 Naive UI 自动获得新特性
- Bug 由社区维护

---

## 🔧 高级功能示例

### 文件树搜索过滤
```vue
<n-input v-model:value="pattern" placeholder="搜索文件..." />
<n-tree
  :data="treeData"
  :pattern="pattern"
  :show-irrelevant-nodes="false"
/>
```

### 虚拟滚动（大数据优化）
```vue
<n-tree
  :data="treeData"
  virtual-scroll
  :style="{ maxHeight: '400px' }"
/>
```

### 自定义右键菜单
```vue
<n-dropdown
  :options="contextMenuOptions"
  :show="showDropdown"
  :x="dropdownX"
  :y="dropdownY"
>
  <n-tree ... />
</n-dropdown>
```

---

## ❓ 常见问题

**Q: NTree 支持拖拽排序吗？**  
A: 支持！设置 `:draggable="true"` 并监听 `@drop` 事件。

**Q: 可以自定义节点渲染吗？**  
A: 可以！使用 `:render-label`、`:render-prefix`、`:render-suffix`。

**Q: 右键菜单如何实现？**  
A: 使用 `NDropdown` 配合 `:node-props` 的 `onContextmenu`。

**Q: 性能如何？**  
A: Naive UI 内置虚拟滚动，支持数万条数据流畅渲染。

---

## 📚 参考文档

- [NTree 组件](https://www.naiveui.com/zh-CN/os-theme/components/tree)
- [NList 组件](https://www.naiveui.com/zh-CN/os-theme/components/list)
- [NDropdown 组件](https://www.naiveui.com/zh-CN/os-theme/components/dropdown)
- [深色主题](https://www.naiveui.com/zh-CN/dark/docs/customize-theme)

---

## ✅ 总结

**强烈建议迁移！** 收益远大于成本：
- ✅ 代码量减少 60-90%
- ✅ 深浅色自动适配，删除 400 行 CSS
- ✅ 功能更强大（搜索、虚拟滚动、键盘导航）
- ✅ 统一的设计语言
- ✅ 更少的维护成本

预计总迁移时间：**3-4 小时**  
代码质量提升：**巨大** 🚀
