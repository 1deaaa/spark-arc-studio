<template>
  <div v-if="isDirector" class="chat-file-import-button">
    <input
      type="file"
      ref="fileInput"
      style="display: none"
      :accept="accept"
      multiple
      @change="handleFileChange"
    />
    <!-- 已附加文件：点击按钮弹出附件管理面板（多附件场景下展示列表 + chunk size 设置）-->
    <n-popover
      v-if="hasAttachment && !importing"
      v-model:show="popoverShow"
      trigger="click"
      placement="top-start"
      :width="320"
      :show-arrow="false"
    >
      <template #trigger>
        <n-button
          quaternary
          circle
          size="small"
          class="chat-file-import-button__trigger chat-file-import-button__trigger--active"
          :title="attachmentBadgeTitle"
        >
          <template #icon>
            <n-icon :size="16"><FileText /></n-icon>
          </template>
          <span v-if="attachmentCount > 1" class="chat-file-import-button__badge">{{ attachmentCount }}</span>
        </n-button>
      </template>
      <div class="chat-attachment-popover">
        <div class="chat-attachment-popover__title">{{ panelTitle }}</div>

        <!-- 附件列表：每行 文件名 / 描述 / 删除按钮 -->
        <ul class="chat-attachment-popover__list">
          <li
            v-for="(item, idx) in attachments"
            :key="item.attachmentId"
            class="chat-attachment-item"
          >
            <div class="chat-attachment-item__main">
              <div class="chat-attachment-item__name" :title="item.filename">{{ item.filename }}</div>
              <div class="chat-attachment-item__desc">{{ attachmentDescriptions[idx] }}</div>
            </div>
            <n-button
              size="tiny"
              quaternary
              circle
              :title="t('components.chatPanel.removeImportedFile')"
              @click="onRemoveAttachmentClick(item.attachmentId)"
            >
              <template #icon>
                <n-icon :size="14"><X /></n-icon>
              </template>
            </n-button>
          </li>
        </ul>

        <div class="chat-attachment-popover__actions">
          <n-button size="small" @click="onAddMoreClick">
            {{ t('components.chatPanel.addMoreAttachment') }}
          </n-button>
        </div>

        <!-- 项目级滑动窗口（chunk size）设置 -->
        <div class="chat-attachment-popover__divider" />
        <div class="chat-attachment-popover__section-title">
          {{ t('components.chatPanel.chunkTokensSettingTitle') }}
        </div>
        <div class="chat-attachment-popover__hint">
          {{ chunkTokensHintText }}
        </div>
        <div class="chat-attachment-popover__chunk-row">
          <n-input-number
            v-model:value="chunkTokensDraft"
            :min="chunkTokensSetting.min"
            :max="chunkTokensSetting.max"
            :step="1000"
            size="small"
            :disabled="chunkTokensSettingLoading || chunkTokensSettingSaving"
            class="chat-attachment-popover__chunk-input"
          />
          <n-button
            size="small"
            type="primary"
            :loading="chunkTokensSettingSaving"
            :disabled="!chunkTokensDirty"
            @click="onSaveChunkTokens"
          >
            {{ t('components.chatPanel.chunkTokensSaveButton') }}
          </n-button>
        </div>
      </div>
    </n-popover>

    <!-- 无附件 / 正在导入：保持原 paperclip 按钮 + tooltip -->
    <n-tooltip v-else trigger="hover">
      <template #trigger>
        <n-button
          quaternary
          circle
          size="small"
          class="chat-file-import-button__trigger"
          :loading="importing"
          @click="onClickButton"
        >
          <template #icon>
            <n-icon :size="16"><Paperclip /></n-icon>
          </template>
        </n-button>
      </template>
      {{ importing ? t('components.chatPanel.cancelImport') : t('components.chatPanel.attachFile') }}
    </n-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NInputNumber, NPopover, NTooltip } from 'naive-ui';
import { FileText, Paperclip, X } from '@lucide/vue';
import { useChatFileImport } from '@/composables/useChatFileImport';

const props = defineProps<{
  sessionId: number | null | undefined;
  agentId?: string | null;
}>();

const isDirector = computed(() => props.agentId === 'agent_director');

const { t } = useI18n();
const {
  fileInput,
  accept,
  importing,
  attachments,
  attachmentDescriptions,
  handleFileChange,
  openImportPicker,
  cancelImport,
  removeImportedContext,
  chunkTokensSetting,
  chunkTokensSettingLoading,
  chunkTokensSettingSaving,
  saveChunkTokensSetting,
} = useChatFileImport(() => props.sessionId);

const popoverShow = ref(false);
const attachmentCount = computed(() => attachments.value.length);
const hasAttachment = computed(() => attachmentCount.value > 0);

const panelTitle = computed(() => {
  if (attachmentCount.value <= 1) return t('components.chatPanel.attachmentPanelTitle');
  return t('components.chatPanel.attachmentListTitle', { count: attachmentCount.value });
});

const attachmentBadgeTitle = computed(() => panelTitle.value);

// chunk size 设置：草稿值跟随 setting 变化；用户编辑后变 dirty。
const chunkTokensDraft = ref<number>(chunkTokensSetting.value.chunkTokens);
watch(
  () => chunkTokensSetting.value.chunkTokens,
  (next) => {
    chunkTokensDraft.value = next;
  },
);

const chunkTokensDirty = computed(() => {
  const draft = Number(chunkTokensDraft.value || 0);
  return draft > 0 && draft !== chunkTokensSetting.value.chunkTokens;
});

const chunkTokensHintText = computed(() =>
  t('components.chatPanel.chunkTokensSettingHint', {
    min: chunkTokensSetting.value.min,
    max: chunkTokensSetting.value.max,
  }),
);

function onClickButton() {
  if (importing.value) {
    cancelImport();
    return;
  }
  openImportPicker();
}

function onAddMoreClick() {
  // 不关闭 popover：让用户连续上传更多文件
  openImportPicker();
}

async function onRemoveAttachmentClick(attachmentId: string) {
  await removeImportedContext(attachmentId);
  // 若删完最后一个附件，关闭 popover；保持 ≥1 时停留以便继续操作。
  if (attachmentCount.value === 0) {
    popoverShow.value = false;
  }
}

async function onSaveChunkTokens() {
  const value = Number(chunkTokensDraft.value || 0);
  if (!Number.isFinite(value) || value <= 0) return;
  await saveChunkTokensSetting(value);
}
</script>

<style scoped>
.chat-file-import-button {
  display: flex;
  align-items: center;
}

.chat-file-import-button__trigger {
  flex-shrink: 0;
  position: relative;
}

/* 已附加文件时：按钮高亮以提示状态 */
.chat-file-import-button__trigger--active {
  background: color-mix(in srgb, var(--spark-primary) 14%, transparent);
  color: var(--spark-primary);
}

.chat-file-import-button__badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--spark-primary, #2080f0);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
  pointer-events: none;
}

.chat-attachment-popover {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 2px 0;
}

.chat-attachment-popover__title {
  font-size: 11px;
  color: var(--spark-text-3, var(--n-text-color-disabled));
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chat-attachment-popover__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 260px;
  overflow-y: auto;
}

.chat-attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 4px;
  border-radius: 6px;
  background: var(--n-action-color, transparent);
}

.chat-attachment-item:hover {
  background: color-mix(in srgb, var(--spark-primary) 6%, transparent);
}

.chat-attachment-item__main {
  flex: 1 1 auto;
  min-width: 0;
}

.chat-attachment-item__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--spark-text-1, var(--n-text-color));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-attachment-item__desc {
  font-size: 11px;
  color: var(--spark-text-3, var(--n-text-color-disabled));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-attachment-popover__actions {
  display: flex;
  gap: 8px;
  margin-top: 2px;
  justify-content: flex-end;
}

.chat-attachment-popover__divider {
  height: 1px;
  background: color-mix(in srgb, var(--spark-text-3, currentColor) 12%, transparent);
  margin: 4px 0 2px;
}

.chat-attachment-popover__section-title {
  font-size: 11px;
  color: var(--spark-text-3, var(--n-text-color-disabled));
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chat-attachment-popover__hint {
  font-size: 11px;
  color: var(--spark-text-3, var(--n-text-color-disabled));
}

.chat-attachment-popover__chunk-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-attachment-popover__chunk-input {
  flex: 1 1 auto;
  min-width: 0;
}
</style>
