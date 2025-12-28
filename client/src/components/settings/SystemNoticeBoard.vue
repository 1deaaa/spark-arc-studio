<template>
    <div class="settings-section notice-board">
        <div class="notice-header">
            <h3>公告板 / Notice Board</h3>
            <n-tag type="info" size="small" round>NEW</n-tag>
        </div>
        <div class="notice-content-wrapper">
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

.notice-board {
    background: linear-gradient(to bottom right, var(--spark-panel-bg), color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 5%));
    border-left: 4px solid var(--spark-primary);
}

.notice-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}

.notice-header h3 {
    margin: 0 !important;
}

.notice-content-wrapper {
    max-height: 400px;
    overflow-y: auto;
    font-size: 14px;
    line-height: 1.6;
    color: var(--spark-text);
}

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
