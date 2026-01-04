<template>
    <div class="settings-section">
        <h3>外观设置</h3>
        <p class="section-desc">自定义主题主色与全局字体（字号与具体风格仍由各处样式控制）。</p>

        <n-form label-placement="left" label-width="90">
            <div class="appearance-grid">
                <n-form-item label="暗色主色">
                    <div class="color-picker-column">
                        <n-color-picker v-model:value="themePrimaryColorDark" :show-alpha="false" :modes="['hex']" />
                        <div class="color-presets">
                            <div
                                v-for="color in darkPresets"
                                :key="color"
                                class="preset-dot"
                                :style="{ backgroundColor: color }"
                                @click="themePrimaryColorDark = color"
                                :title="color"
                            ></div>
                        </div>
                    </div>
                </n-form-item>
                <n-form-item label="亮色主色">
                    <div class="color-picker-column">
                        <n-color-picker v-model:value="themePrimaryColorLight" :show-alpha="false" :modes="['hex']" />
                        <div class="color-presets">
                            <div
                                v-for="color in lightPresets"
                                :key="color"
                                class="preset-dot"
                                :style="{ backgroundColor: color }"
                                @click="themePrimaryColorLight = color"
                                :title="color"
                            ></div>
                        </div>
                    </div>
                </n-form-item>
                <n-form-item label="全局字体" class="appearance-font">
                    <n-select
                        v-model:value="fontFamily"
                        :options="fontOptions"
                        :render-label="renderFontOptionLabel"
                        filterable
                        tag
                        :on-create="handleCreateFontOption"
                        placeholder="选择或输入字体正式名称"
                    />
                    <div class="hint-text">
                        提示：Windows 可在“设置 → 个性化 → 字体”里获取正式字体名称；移动端请在系统字体列表/中查正式名。
                    </div>
                </n-form-item>
            </div>

            <div class="appearance-preview">
                <n-text depth="3">预览：</n-text>
                <div class="preview-text">春江花月夜 · The quick brown fox jumps over the lazy dog · 1234567890</div>
            </div>
        </n-form>
    </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, h } from 'vue';
import { NForm, NFormItem, NColorPicker, NSelect, NText } from 'naive-ui';
import { useThemeStore } from '../stores/themeStore';

const themeStore = useThemeStore();

const darkPresets = [
    '#7aa2f7', // 星空蓝 (默认)
    '#bd93f9', // 星云紫
    '#50fa7b', // 极光绿
    '#ff9e64', // 晚霞橙
    '#f7768e', // 蔷薇红
    '#00b8d4', // 赛博蓝
];

const lightPresets = [
    '#6b9080', // 鼠尾草绿 (默认)
    '#e07a5f', // 珊瑚色
    '#3d5a80', // 灰蓝
    '#81b29a', // 湖水绿
    '#e9c46a', // 沙漠黄
    '#8a5a44', // 红土褐
];

const PLATFORM = {
    windows: 'windows',
    android: 'android',
    ios: 'ios',
    linux: 'linux',
};

const platformEmoji = (p) => {
    if (p === PLATFORM.windows) return '💻';
    if (p === PLATFORM.android) return '📱';
    if (p === PLATFORM.ios) return '🍎';
    if (p === PLATFORM.linux) return '🐧';
    return '';
};

const PlatformIcon = (p) => {
    const emoji = platformEmoji(p);
    if (emoji) return h('span', { class: 'platform-emoji', title: emoji }, emoji);
    return null;
};

const makeFontOption = (label, value, platforms) => ({
    label,
    value,
    platforms,
});

const fontOptions = [
    makeFontOption('跟随浏览器', '', [PLATFORM.windows, PLATFORM.android, PLATFORM.ios, PLATFORM.linux]),
    makeFontOption('Segoe UI', 'Segoe UI', [PLATFORM.windows]),
    makeFontOption('Segoe UI Emoji', 'Segoe UI Emoji', [PLATFORM.windows]),
    makeFontOption('Segoe UI Symbol', 'Segoe UI Symbol', [PLATFORM.windows]),
    makeFontOption('Microsoft YaHei / 微软雅黑', 'Microsoft YaHei', [PLATFORM.windows]),
    makeFontOption('Microsoft YaHei UI', 'Microsoft YaHei UI', [PLATFORM.windows]),
    makeFontOption('SimSun / 宋体', 'SimSun', [PLATFORM.windows]),
    makeFontOption('SimHei / 黑体', 'SimHei', [PLATFORM.windows]),
    makeFontOption('KaiTi / 楷体', 'KaiTi', [PLATFORM.windows]),
    makeFontOption('FangSong / 仿宋', 'FangSong', [PLATFORM.windows]),
    makeFontOption('Yu Gothic', 'Yu Gothic', [PLATFORM.windows]),
    makeFontOption('Arial', 'Arial', [PLATFORM.windows, PLATFORM.android, PLATFORM.ios]),
    makeFontOption('Times New Roman', 'Times New Roman', [PLATFORM.windows, PLATFORM.ios]),
    makeFontOption('Courier New', 'Courier New', [PLATFORM.windows, PLATFORM.ios]),
    makeFontOption('Consolas', 'Consolas', [PLATFORM.windows]),
    makeFontOption('Tahoma', 'Tahoma', [PLATFORM.windows]),
    makeFontOption('Verdana', 'Verdana', [PLATFORM.windows, PLATFORM.ios]),
    makeFontOption('DejaVu Sans', 'DejaVu Sans', [PLATFORM.linux]),
    makeFontOption('DejaVu Serif', 'DejaVu Serif', [PLATFORM.linux]),
    makeFontOption('DejaVu Sans Mono', 'DejaVu Sans Mono', [PLATFORM.linux]),
    makeFontOption('Liberation Sans', 'Liberation Sans', [PLATFORM.linux]),
    makeFontOption('Liberation Serif', 'Liberation Serif', [PLATFORM.linux]),
    makeFontOption('Liberation Mono', 'Liberation Mono', [PLATFORM.linux]),
    makeFontOption('Cantarell', 'Cantarell', [PLATFORM.linux]),
    makeFontOption('Ubuntu', 'Ubuntu', [PLATFORM.linux]),
    makeFontOption('Roboto', 'Roboto', [PLATFORM.android]),
    makeFontOption('Roboto Condensed', 'Roboto Condensed', [PLATFORM.android]),
    makeFontOption('Noto Sans', 'Noto Sans', [PLATFORM.android, PLATFORM.linux]),
    makeFontOption('Noto Sans CJK SC', 'Noto Sans CJK SC', [PLATFORM.android]),
    makeFontOption('Noto Serif', 'Noto Serif', [PLATFORM.android]),
    makeFontOption('PingFang SC / 苹方', 'PingFang SC', [PLATFORM.ios]),
    makeFontOption('Heiti SC / 黑体-简', 'Heiti SC', [PLATFORM.ios]),
    makeFontOption('Hiragino Sans GB', 'Hiragino Sans GB', [PLATFORM.ios]),
    makeFontOption('Helvetica Neue', 'Helvetica Neue', [PLATFORM.ios]),
    makeFontOption('Menlo', 'Menlo', [PLATFORM.ios]),
];

const themePrimaryColorDark = ref('');
const themePrimaryColorLight = ref('');
const fontFamily = ref('');

const syncAppearanceFromStore = async () => {
    fontFamily.value = themeStore.fontFamily || '';
    if (themeStore.primaryColorDark) themePrimaryColorDark.value = themeStore.primaryColorDark;
    if (themeStore.primaryColorLight) themePrimaryColorLight.value = themeStore.primaryColorLight;

    await nextTick();
    const current = getComputedStyle(document.documentElement).getPropertyValue('--spark-primary').trim();
    if (!themePrimaryColorDark.value) themePrimaryColorDark.value = current || '#7aa2f7';
    if (!themePrimaryColorLight.value) themePrimaryColorLight.value = '#6b9080';
};

watch(themePrimaryColorDark, (val) => {
    themeStore.setPrimaryColorDark((val || '').toString().trim());
});

watch(themePrimaryColorLight, (val) => {
    themeStore.setPrimaryColorLight((val || '').toString().trim());
});

watch(fontFamily, (val) => {
    themeStore.setFontFamily(val);
});

onMounted(async () => {
    await syncAppearanceFromStore();
});

watch(
    () => [themeStore.themeMode, themeStore.prefersDark, themeStore.primaryColorDark, themeStore.primaryColorLight, themeStore.fontFamily, themeStore.fontKey],
    () => {
        syncAppearanceFromStore();
    }
);

const handleCreateFontOption = (label) => {
    const v = (label || '').toString().trim();
    if (!v) return null;
    return makeFontOption(v, v, []);
};

const renderFontOptionLabel = (option) => {
    const platforms = Array.isArray(option?.platforms) ? option.platforms : [];
    return h('div', { class: 'font-option' }, [
        h('span', { class: 'font-option-name' }, option.label),
        h('span', { class: 'font-option-platforms' }, platforms.map(p => PlatformIcon(p)).filter(Boolean)),
    ]);
};
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    padding: 24px;
    margin-bottom: 24px;
}

.settings-section h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    color: var(--spark-primary);
    -webkit-user-select: none;
    user-select: none;
    cursor: default;
}

.section-desc {
    color: var(--spark-text-muted);
    margin-bottom: 20px;
    font-size: 14px;
}

.appearance-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.appearance-font {
    grid-column: 1 / -1;
}

.color-picker-column {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
}

.color-presets {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 4px;
}

.preset-dot {
    width: 24px;
    height: 24px;
    border-radius: 8px;
    cursor: pointer;
    border: 2px solid transparent;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--spark-shadow-sm);
}

.preset-dot:hover {
    transform: scale(1.15) translateY(-2px);
    border-color: var(--spark-primary);
    box-shadow: 0 4px 12px var(--spark-primary-glow);
}

.hint-text {
    margin-top: 6px;
    font-size: 12px;
    color: var(--spark-text-muted);
}

.font-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
}

.font-option-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.font-option-platforms {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: color-mix(in srgb, var(--spark-text-muted), var(--spark-primary) 18%);
}

.platform-emoji {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid color-mix(in srgb, var(--spark-border), transparent 10%);
    background: color-mix(in srgb, var(--spark-panel-bg), transparent 18%);
    font-size: 13px;
    line-height: 1;
}

.appearance-preview {
    margin-top: 8px;
}

.preview-text {
    margin-top: 8px;
    padding: 10px 12px;
    border-radius: var(--spark-radius-sm);
    border: 1px solid var(--spark-border);
    background: var(--spark-bg);
    color: var(--spark-text);
}

@media (max-width: 1100px) {
    .appearance-grid {
        grid-template-columns: 1fr;
    }
}
</style>
