<template>
  <div class="right-panel-section" :class="{ 'is-embedded': embedded }" v-show="visible">
    <n-card 
      :title="t('views.characters.aiAdjustTitle')"
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-button 
          size="tiny" 
          type="primary" 
          @click="handleAdjust" 
          :loading="generating"
          :disabled="!suggestion.trim()"
        >
          <template #icon>
            <n-icon :component="Rocket" />
          </template>
          {{ t('views.characters.aiAdjustAction') }}
        </n-button>
      </template>

      <n-form label-placement="top" size="medium">
          <StudioSeamlessTextarea
            v-model:value="suggestion"
            :autosize="{ minRows: 12, maxRows: 24 }"
            :placeholder="t('views.characters.aiAdjustPlaceholder')"
            :show-count="true"
            :maxlength="800"
          />

      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCard, NForm, NButton, NIcon } from 'naive-ui';
import { Rocket } from '@lucide/vue';
import StudioSeamlessTextarea from '@/components/editors/StudioSeamlessTextarea.vue';
import { fetchWithAuth } from '@/services/api';
import { fetchCharacters } from '@/services/storyService';
import { sendChatMessageStream } from '@/services/chatService';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';
import { createStreamingTask, consumeNdjsonReader, isAbortLikeError, createThinkStreamParser } from '@/utils/streamingRuntime';
import type { StoryCharacterDetail } from '@/services/aiContracts';
import { buildCreativeCacheKey, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';

type ChatStreamEvent = {
  event?: string;
  text?: string;
  tool_name?: string;
  toolName?: string;
  [key: string]: unknown;
};

defineProps({
  visible: { type: Boolean, default: false },
  embedded: { type: Boolean, default: false }
});
const projectStore = useProjectStore();
const { t } = useI18n();

const suggestion = ref('');
const generating = ref(false);

function buildSuggestionCacheKey() {
  return buildCreativeCacheKey('character-adjust-suggestion', projectStore.currentProject);
}

watch(suggestion, (value) => {
  if (!projectStore.currentProject) return;
  saveCreativeCache(buildSuggestionCacheKey(), value);
});

watch(() => projectStore.currentProject, (projectName) => {
  suggestion.value = loadCreativeCache<string>(buildCreativeCacheKey('character-adjust-suggestion', projectName)) || '';
}, { immediate: true });

function normalizeToolName(rawToolName: unknown = '') {
  const normalized = String(rawToolName || '').trim().toLowerCase();
  if (!normalized) return '';
  const key = normalized.replace(/[\s_-]/g, '');
  const aliases = {
    rewriteallcharacters: 'rewrite_all_characters',
    rewritecharacters: 'rewrite_all_characters',
    rewritecharacter: 'update_character',
    updatecharacter: 'update_character',
  };
  return aliases[key] || normalized;
}

async function buildActiveContext(projectName: string): Promise<string> {
  let worldview = '';
  let charactersText = '';

  try {
    const res = await fetchWithAuth(`/api/worldview/${encodeURIComponent(projectName)}`);
    if (res.ok) {
      const data = await res.json();
      worldview = (data?.content || '').trim();
    }
  } catch {}

  try {
    const characters = await fetchCharacters(projectName, true) as StoryCharacterDetail[];
    charactersText = (characters || [])
      .filter(ch => ![-1, -2].includes(Number(ch.id)))
      .map(ch => {
        const name = (ch.name || t('views.characters.characterFallback', { id: ch.id })).trim();
        const content = (ch.content || '').trim();
        return `- ${name}:\n${content}`;
      })
      .join('\n\n');
  } catch {}

  return [
    worldview ? `【当前世界观】\n${worldview}` : '',
    charactersText ? `【当前角色设定】\n${charactersText}` : '',
  ].filter(Boolean).join('\n\n');
}

async function handleAdjust() {
  const projectName = projectStore.currentProject;
  if (!projectName) {
    bus.emit('toast', { type: 'error', message: t('views.characters.selectProject') });
    return;
  }

  const suggestionText = (suggestion.value || '').trim();
  if (!suggestionText) {
    bus.emit('toast', { type: 'warning', message: t('views.characters.enterAiRequest') });
    return;
  }

  generating.value = true;
  let executed = false;
  let assistantText = '';
  const thinkParser = createThinkStreamParser();
  const task = createStreamingTask('world', {
    target: 'characters',
    text: t('views.characters.aiAnalyzing'),
    canCancel: true,
    autoStart: false,
    onCancel: () => {
      generating.value = false;
      bus.emit('toast', { type: 'info', message: t('views.characters.aiCancelled') });
    },
  });

  const message = [
    '你正在执行【工具箱：修改角色设定】任务。',
    '请基于下方修改意见，自主判断并调用 update_character 或 rewrite_all_characters 工具完成落盘。',
    '新增、补全或涉及多个角色时，必须调用 rewrite_all_characters 并传 append=true；修改单个已有角色时必须调用 update_character。',
    '只有修改意见明确要求清空重做或整体替换全部角色时，才允许调用 rewrite_all_characters 并传 append=false。',
    '我已经明确确认执行，你不需要再次询问确认。',
    '请直接执行工具，不要仅输出建议。',
    '',
    '【修改意见】',
    suggestionText,
  ].join('\n');

  try {
    task.start(t('views.characters.aiAnalyzing'));
    const activeContext = await buildActiveContext(projectName);
    const reader = await sendChatMessageStream(
      projectName,
      'agent_lorebook',
      'global',
      message,
      null,
      activeContext,
      null,
      task.signal,
    );

    await consumeNdjsonReader(reader, {
      signal: task.signal,
      onEvent: (evt: ChatStreamEvent) => {
        const eventType = evt.event;
        const toolName = normalizeToolName(evt.tool_name || evt.toolName || '');
        if (eventType === 'assistant_delta') {
          assistantText += thinkParser.push(evt.text || '').display;
          return;
        }
        if (eventType === 'tool_intent_started' || eventType === 'tool_exec_started') {
          if (toolName === 'rewrite_all_characters' || toolName === 'update_character') {
            task.start(toolName === 'update_character'
              ? t('views.characters.aiUpdatingOne')
              : t('views.characters.aiUpdatingBatch'));
          }
          return;
        }
        if (eventType === 'tool_exec_finished') {
          if (toolName === 'rewrite_all_characters' || toolName === 'update_character') {
            executed = true;
            task.hide();
          }
        }
      },
      onMalformedLine: (raw) => {
        assistantText += thinkParser.push(raw).display;
      }
    });

    assistantText += thinkParser.flush().display;

    if (task.aborted) return;

    if (executed) {
      bus.emit('lorebook-refresh-characters');
      bus.emit('lorebook-refresh');
      bus.emit('toast', { type: 'success', message: t('views.characters.aiUpdated') });
      suggestion.value = '';
      saveCreativeCache(buildSuggestionCacheKey(), '');
    } else {
      bus.emit('toast', { type: 'warning', message: assistantText.trim() || t('views.characters.aiNoTool') });
    }
  } catch (e: unknown) {
    if (isAbortLikeError(e)) return;
    const errorMessage = e instanceof Error ? e.message : t('views.characters.aiFailed');
    bus.emit('toast', { type: 'error', message: errorMessage || t('views.characters.aiFailed') });
  } finally {
    task.dispose();
    generating.value = false;
  }
}
</script>

<style scoped>
.right-panel-section {
  padding: 0;
}

.right-panel-section.is-embedded {
  padding: 0;
}

.right-panel-section.is-embedded :deep(.n-card) {
  background-color: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius) !important;
  box-shadow: none !important;
}

.right-panel-section.is-embedded :deep(.n-card__header) {
  padding: 8px 8px 6px !important;
}

.right-panel-section.is-embedded :deep(.n-card-header__main) {
  font-size: var(--spark-fs-base);
  line-height: 1.2;
}

.right-panel-section.is-embedded :deep(.n-card-content) {
  padding: 0 !important;
}

.right-panel-section.is-embedded :deep(.n-card__action) {
  padding: 8px 8px 8px !important;
}

.right-panel-section.is-embedded :deep(.studio-seamless-textarea) {
  width: 100%;
}
</style>
