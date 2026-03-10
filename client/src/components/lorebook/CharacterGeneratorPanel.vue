<template>
  <div class="right-panel-section" :class="{ 'is-embedded': embedded }" v-show="visible">
    <n-card 
      title="修改角色设定" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon :component="SparklesOutline" size="20" />
      </template>

      <n-form label-placement="top" size="medium">
        <n-form-item label="修改意见">
          <n-input
            v-model:value="suggestion"
            type="textarea"
            :autosize="{ minRows: 12, maxRows: 24 }"
            placeholder="在这里输入你的修改意见：角色名字应该更古风，角色A的设定应该更温柔，角色B应更克制并避免极端设定..."
            show-count
            maxlength="800"
          />
        </n-form-item>

        <n-button 
          type="primary" 
          @click="handleAdjust" 
          :loading="generating"
          :disabled="!suggestion.trim()"
          block
          strong
          size="large"
        >
          <template #icon>
            <n-icon :component="RocketOutline" />
          </template>
          开始调整
        </n-button>

      </n-form>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NCard, NForm, NFormItem, NInput, NButton, NIcon } from 'naive-ui';
import { SparklesOutline, RocketOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';
import { fetchCharacters } from '@/services/storyService';
import { sendChatMessageStream } from '@/services/chatService';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';
import { createStreamingTask, consumeNdjsonReader, isAbortLikeError } from '@/utils/streamingRuntime';

defineProps({
  visible: { type: Boolean, default: false },
  embedded: { type: Boolean, default: false }
});
const projectStore = useProjectStore();

const suggestion = ref('');
const generating = ref(false);

function normalizeToolName(rawToolName = '') {
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

async function buildActiveContext(projectName) {
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
    const characters = await fetchCharacters(projectName, true);
    charactersText = (characters || [])
      .filter(ch => ch.id !== -1)
      .map(ch => {
        const name = (ch.name || `角色 ${ch.id}`).trim();
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
    bus.emit('toast', { type: 'error', message: '请选择项目' });
    return;
  }

  const suggestionText = (suggestion.value || '').trim();
  if (!suggestionText) {
    bus.emit('toast', { type: 'warning', message: '请先输入修改意见' });
    return;
  }

  generating.value = true;
  let executed = false;
  let assistantText = '';
  const task = createStreamingTask('world', {
    target: 'characters',
    text: '正在更新角色设定...',
    canCancel: true,
    autoStart: false,
    onCancel: () => {
      generating.value = false;
      bus.emit('toast', { type: 'info', message: '已取消角色调整' });
    },
  });

  const message = [
    '你正在执行【工具箱：修改角色设定】任务。',
    '请基于下方修改意见，自主判断并调用 update_character 或 rewrite_all_characters 工具完成落盘。',
    '我已经明确确认执行，你不需要再次询问确认。',
    '请直接执行工具，不要仅输出建议。',
    '',
    '【修改意见】',
    suggestionText,
  ].join('\n');

  try {
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
      onEvent: (evt) => {
        const eventType = evt.event;
        const toolName = normalizeToolName(evt.tool_name || evt.toolName || '');
        if (eventType === 'assistant_delta') {
          assistantText += evt.text || '';
          return;
        }
        if (eventType === 'tool_intent_started' || eventType === 'tool_exec_started') {
          if (toolName === 'rewrite_all_characters' || toolName === 'update_character') {
            task.start(toolName === 'update_character' ? '正在更新角色设定...' : '正在重写角色设定...');
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
        assistantText += raw;
      }
    });

    if (task.aborted) return;

    if (executed) {
      bus.emit('lorebook-refresh-characters');
      bus.emit('lorebook-refresh');
      bus.emit('toast', { type: 'success', message: '角色设定已更新' });
      suggestion.value = '';
    } else {
      bus.emit('toast', { type: 'warning', message: assistantText.trim() || '本次未执行角色修改工具，请调整描述后重试' });
    }
  } catch (e) {
    if (isAbortLikeError(e)) return;
    bus.emit('toast', { type: 'error', message: e?.message || '调整失败' });
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
  background-color: transparent;
}
</style>
