<template>
    <div class="settings-section">
        <h3>外观设置</h3>
        <p class="section-desc">自定义主题主色与全局字体（字号与具体风格仍由各处样式控制）。</p>

        <n-form label-placement="left" label-width="80">
            <div class="appearance-rows">
                <n-form-item label="暗色主色">
                    <div class="color-picker-row">
                        <n-popover trigger="click" placement="bottom-start" :show-arrow="false">
                            <template #trigger>
                                <div class="color-swatch" :style="{ backgroundColor: themePrimaryColorDark }">
                                    <span class="swatch-hex">{{ themePrimaryColorDark }}</span>
                                </div>
                            </template>
                            <n-color-picker
                                v-model:value="themePrimaryColorDark"
                                :show-alpha="false"
                                :modes="['hex']"
                                style="width: 240px;"
                            />
                        </n-popover>
                        <div class="color-presets-inline">
                            <div
                                v-for="color in darkPresets"
                                :key="color"
                                class="preset-dot-small"
                                :class="{ active: themePrimaryColorDark === color }"
                                :style="{ backgroundColor: color }"
                                @click="themePrimaryColorDark = color"
                                :title="color"
                            ></div>
                        </div>
                    </div>
                </n-form-item>
                <n-form-item label="亮色主色">
                    <div class="color-picker-row">
                        <n-popover trigger="click" placement="bottom-start" :show-arrow="false">
                            <template #trigger>
                                <div class="color-swatch" :style="{ backgroundColor: themePrimaryColorLight }">
                                    <span class="swatch-hex">{{ themePrimaryColorLight }}</span>
                                </div>
                            </template>
                            <n-color-picker
                                v-model:value="themePrimaryColorLight"
                                :show-alpha="false"
                                :modes="['hex']"
                                style="width: 240px;"
                            />
                        </n-popover>
                        <div class="color-presets-inline">
                            <div
                                v-for="color in lightPresets"
                                :key="color"
                                class="preset-dot-small"
                                :class="{ active: themePrimaryColorLight === color }"
                                :style="{ backgroundColor: color }"
                                @click="themePrimaryColorLight = color"
                                :title="color"
                            ></div>
                        </div>
                    </div>
                </n-form-item>
                <n-form-item label="全局字体" class="appearance-font">
                    <div class="font-select-row">
                        <n-select
                            v-model:value="fontFamily"
                            :options="fontOptions"
                            :render-label="renderFontOptionLabel"
                            filterable
                            tag
                            :on-create="handleCreateFontOption"
                            placeholder="选择或输入字体正式名称"
                        />
                        <n-tooltip
                            trigger="manual"
                            placement="top"
                            :show="showFontHint"
                            :show-arrow="true"
                        >
                            <template #trigger>
                                <n-icon
                                    class="info-icon"
                                    @mouseenter="onFontHintEnter"
                                    @mouseleave="onFontHintLeave"
                                    @click.stop="toggleFontHint"
                                >
                                    <InformationCircleOutline />
                                </n-icon>
                            </template>
                            提示：Windows 可在“设置 → 个性化 → 字体”里获取正式字体名称；移动端请在系统字体列表/中查正式名。
                        </n-tooltip>
                    </div>
                </n-form-item>
            </div>

            <div class="appearance-preview">
                <n-text depth="3">预览：</n-text>
                <div class="preview-text">三月秋分 · Mournight · 2026</div>
            </div>
        </n-form>
    </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, h } from 'vue';
import { NForm, NFormItem, NColorPicker, NSelect, NText, NTooltip, NIcon, NPopover } from 'naive-ui';
import { InformationCircleOutline } from '@vicons/ionicons5';
import { useThemeStore } from '../stores/themeStore';

const themeStore = useThemeStore();

const showFontHint = ref(false);
const pinFontHint = ref(false);

function onFontHintEnter() {
    showFontHint.value = true;
}

function onFontHintLeave() {
    if (!pinFontHint.value) {
        showFontHint.value = false;
    }
}

function toggleFontHint() {
    pinFontHint.value = !pinFontHint.value;
    showFontHint.value = pinFontHint.value;
}

// 暗色模式预制颜色 - 适合深色背景，亮度适中不刺眼，覆盖全色系
const darkPresets = [
    '#7aa2f7', // 星空蓝 (默认) - 经典冷静
    '#bb9af7', // 薰衣草紫 - 优雅神秘
    '#9ece6a', // 抹茶绿 - 自然清新
    '#ff9e64', // 晚霞橙 - 温暖活力
    '#f7768e', // 樱花粉 - 浪漫柔美
    '#2ac3de', // 赛博青 - 科技感
    '#e0af68', // 琥珀金 - 高贵典雅
    '#73daca', // 薄荷绿 - 清凉舒适
];

// 亮色模式预制颜色 - 适合浅色背景，饱和度柔和不刺眼，覆盖全色系
const lightPresets = [
    '#6b9080', // 鼠尾草绿 (默认) - 自然平静
    '#e07a5f', // 珊瑚橙 - 温暖友好
    '#3d5a80', // 靛蓝 - 沉稳专业
    '#81b29a', // 湖水绿 - 清新自然
    '#d4a373', // 焦糖色 - 温馨舒适
    '#7c6a9f', // 紫藤紫 - 优雅含蓄
    '#2a9d8f', // 孔雀绿 - 活力时尚
    '#e76f51', // 陶土红 - 热情沉稳
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

.appearance-rows {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.appearance-font {
    margin-top: 8px;
}

.color-picker-row {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    flex: 1;
}

.color-swatch {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 100px;
    height: 32px;
    border-radius: 6px;
    cursor: pointer;
    border: 1px solid var(--spark-border);
    transition: all 0.2s ease;
    box-shadow: var(--spark-shadow-sm);
}

.color-swatch:hover {
    border-color: var(--spark-primary);
    box-shadow: 0 2px 8px var(--spark-primary-glow);
}

.swatch-hex {
    font-size: 12px;
    font-weight: 500;
    color: white;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
    text-transform: uppercase;
}

.color-presets-inline {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(24px, 1fr));
    gap: 6px;
    width: 100%;
}

.preset-dot-small {
    width: 100%;
    aspect-ratio: 1;
    border-radius: 4px;
    cursor: pointer;
    border: 2px solid transparent;
    transition: all 0.15s ease;
    box-shadow: var(--spark-shadow-sm);
}

.preset-dot-small:hover {
    transform: scale(1.1);
    border-color: var(--spark-primary);
}

.preset-dot-small.active {
    border-color: var(--spark-text);
    box-shadow: 0 0 0 2px var(--spark-bg), 0 0 0 4px var(--spark-primary);
}

.font-select-row {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
}

.info-icon {
    font-size: 16px;
    color: var(--spark-text-muted);
    cursor: help;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: color 0.2s ease;
}

.info-icon:hover {
    color: var(--spark-primary);
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

/* 窄宽度断点 - 移动端 */
@media (max-width: 768px) {
    .settings-section {
        padding: 4px 12px;
        margin-bottom: 8px;
        background: transparent;
        border: none;
        border-radius: 0;
    }
    
    .settings-section h3 {
        font-size: 16px;
    }
    
    .section-desc {
        font-size: 13px;
        margin-bottom: 12px;
    }
    
    .color-swatch {
        min-width: 90px;
        max-width: 140px;
        height: 28px;
    }
    
    .swatch-hex {
        font-size: 11px;
    }
    
    .hint-text {
        font-size: 11px;
    }
    
    .preview-text {
        padding: 8px 10px;
        font-size: 14px;
    }
}

/* 超窄宽度 - 小屏手机 */
@media (max-width: 480px) {
    .settings-section {
        padding: 4px 10px;
    }
}
</style>
