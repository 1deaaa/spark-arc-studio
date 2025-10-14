# Naive UI 深浅色模式使用指南

## ✅ 已实现：自适应系统深浅色模式

当前项目已配置为**自动跟随系统主题**：
- Windows 设置为深色模式 → 应用显示暗色主题
- Windows 设置为浅色模式 → 应用显示亮色主题
- 系统主题切换时，应用会实时响应变化

## 🎨 Naive UI 主题系统说明

### 1. 内置主题
```js
import { darkTheme } from 'naive-ui';

// 在 NConfigProvider 中使用
<n-config-provider :theme="darkTheme">  // 暗色主题
<n-config-provider :theme="null">      // 亮色主题（默认）
```

### 2. 当前实现方式（自适应系统）

```vue
<script setup>
import { ref, computed, onMounted } from 'vue';
import { darkTheme } from 'naive-ui';

const prefersDark = ref(false);

onMounted(() => {
  // 检测系统主题
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  prefersDark.value = mediaQuery.matches;
  
  // 监听系统主题变化
  mediaQuery.addEventListener('change', (e) => {
    prefersDark.value = e.matches;
  });
});

// 动态切换主题
const theme = computed(() => prefersDark.value ? darkTheme : null);
</script>

<template>
  <n-config-provider :theme="theme" :theme-overrides="themeOverrides">
    <!-- 你的应用 -->
  </n-config-provider>
</template>
```

### 3. 手动切换主题（可选实现）

如果你想添加一个手动切换按钮：

```vue
<script setup>
import { ref } from 'vue';
import { darkTheme } from 'naive-ui';

// 用户手动选择的主题
const isDark = ref(false);

// 切换主题
const toggleTheme = () => {
  isDark.value = !isDark.value;
};

const theme = computed(() => isDark.value ? darkTheme : null);
</script>

<template>
  <n-config-provider :theme="theme">
    <n-button @click="toggleTheme">
      {{ isDark ? '☀️ 浅色模式' : '🌙 深色模式' }}
    </n-button>
  </n-config-provider>
</template>
```

### 4. 三种模式混合（系统 + 手动）

```vue
<script setup>
import { ref, computed, onMounted } from 'vue';
import { darkTheme } from 'naive-ui';

// 'auto' | 'light' | 'dark'
const themeMode = ref('auto');
const systemPrefersDark = ref(false);

onMounted(() => {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  systemPrefersDark.value = mediaQuery.matches;
  mediaQuery.addEventListener('change', (e) => {
    systemPrefersDark.value = e.matches;
  });
});

const theme = computed(() => {
  if (themeMode.value === 'dark') return darkTheme;
  if (themeMode.value === 'light') return null;
  // auto 模式：跟随系统
  return systemPrefersDark.value ? darkTheme : null;
});
</script>

<template>
  <n-config-provider :theme="theme">
    <n-space>
      <n-button @click="themeMode = 'light'">☀️ 浅色</n-button>
      <n-button @click="themeMode = 'dark'">🌙 深色</n-button>
      <n-button @click="themeMode = 'auto'">🔄 跟随系统</n-button>
    </n-space>
  </n-config-provider>
</template>
```

## 🎯 主题覆盖（Theme Overrides）

`themeOverrides` 对亮色和暗色主题都生效：

```js
const themeOverrides = {
  common: {
    primaryColor: '#3498db',  // 主色调
    borderRadius: '8px',      // 圆角
    fontFamily: "'Microsoft YaHei', sans-serif"
  },
  Button: {
    borderRadiusMedium: '6px',
    fontWeightStrong: '600'
  }
};
```

## 📱 测试方法

### Windows 11
1. 设置 → 个性化 → 颜色
2. 选择"深色"或"浅色"
3. 刷新页面或等待自动切换

### macOS
1. 系统偏好设置 → 外观
2. 选择"深色"或"浅色"
3. 应用会实时响应

## 💡 最佳实践

1. **默认使用自适应模式**：尊重用户系统设置
2. **提供手动切换选项**：给用户更多控制权
3. **持久化用户选择**：用 `localStorage` 保存用户偏好
4. **避免强制主题**：不要删除 `null`（亮色）主题选项

## 🔗 官方文档
- [Naive UI - Dark Theme](https://www.naiveui.com/zh-CN/dark/docs/customize-theme)
- [Naive UI - Theme Editor](https://www.naiveui.com/zh-CN/dark/docs/theme-editor)
