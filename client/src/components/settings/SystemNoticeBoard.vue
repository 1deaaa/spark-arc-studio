
<template>
    <div class="settings-section notice-board" :class="{ collapsed: isCollapsed }">
        <div class="notice-header" @click="toggleCollapse">
            <div class="header-left">
                <h3>公告板 / Notice Board</h3>
                <n-tag type="info" size="small" round v-if="!isCollapsed">NEW</n-tag>
            </div>
            <div class="header-right">
                <i class="ri-arrow-down-s-line collapse-icon" :class="{ rotated: isCollapsed }"></i>
            </div>
        </div>
        
        <div class="notice-content-wrapper" v-show="!isCollapsed">
            <MarkdownRenderer v-if="noticeContent" :content="noticeContent" />
            <n-skeleton v-else-if="loadingNotice" :repeat="3" text />
            <n-text v-else depth="3">暂无最新公告</n-text>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { NTag, NSkeleton, NText } from 'naive-ui';
import MarkdownRenderer from '../share/MarkdownRenderer.vue';
import { fetchWithAuth } from '../../services/api';

const noticeContent = ref('');
const loadingNotice = ref(false);
const isCollapsed = ref(true); // Default to collapsed as requested

const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
};

const fetchNotice = async () => {
    loadingNotice.value = true;
    try {
        const res = await fetchWithAuth('/api/system/notice');
        if (res.ok) {
            const data = await res.json();
            noticeContent.value = data.content;
        }
    } catch (e) {
        console.error('Failed to fetch notice:', e);
    } finally {
        loadingNotice.value = false;
    }
};

onMounted(() => {
    fetchNotice();
});
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    margin-bottom: 24px;
    display: flex;
    flex-direction: column;
    transition: all 0.3s ease;
    overflow: hidden;
}

.settings-section.collapsed {
    height: auto;
}

.settings-section:not(.collapsed) {
    height: 100%;
}

.notice-board {
    background: linear-gradient(to bottom right, var(--spark-panel-bg), color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 5%));
    border-left: 4px solid var(--spark-primary);
}

.notice-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    cursor: pointer;
    user-select: none;
    flex-shrink: 0;
}

.notice-header:hover {
    background: rgba(255, 255, 255, 0.02);
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.settings-section h3 {
    margin: 0;
    font-size: 16px;
    color: var(--spark-primary);
}

.collapse-icon {
    font-size: 20px;
    color: var(--spark-text-muted);
    transition: transform 0.3s;
}

.collapse-icon.rotated {
    transform: rotate(-90deg);
}

.notice-content-wrapper {
    flex: 1;
    overflow-y: auto;
    font-size: 16px;
    line-height: 1.7;
    color: var(--spark-text);
    padding: 0 24px 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    margin-top: 8px;
    padding-top: 16px;
}

/* Markdown Styles */
.notice-content-wrapper :deep(h1),
.notice-content-wrapper :deep(h2),
.notice-content-wrapper :deep(h3) {
    color: var(--spark-primary);
    margin-top: 16px;
    margin-bottom: 8px;
}

.notice-content-wrapper :deep(ul),
.notice-content-wrapper :deep(ol) {
    padding-left: 20px;
}

.notice-content-wrapper :deep(li) {
    margin-bottom: 4px;
}

.notice-content-wrapper :deep(p) {
    margin-bottom: 12px;
}
</style>
