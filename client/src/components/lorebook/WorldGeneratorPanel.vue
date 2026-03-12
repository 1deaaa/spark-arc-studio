<template>
  <div class="world-gen-panel">
    <n-card 
      title="调整世界观" 
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
            :autosize="{ minRows: 12, maxRows: 15 }"
            placeholder="在这里输入你的修改意见：世界观应严格确保现实为蓝本，某设定应回避，某规则需要更清晰..."
            show-count
            maxlength="800"
          />
        </n-form-item>
        
        <n-button
          type="primary"
          block
          strong
          size="large"
          :loading="generating"
          :disabled="!suggestion.trim()"
          @click="handleAdjust"
        >
          <template #icon>
            <n-icon :component="FlashOutline" />
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
import { SparklesOutline, FlashOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';
import { fetchCharacters } from '@/services/storyService';
import { sendChatMessageStream } from '@/services/chatService';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';
import { createStreamingTask, consumeNdjsonReader, isAbortLikeError, createThinkStreamParser } from '@/utils/streamingRuntime';

const projectStore = useProjectStore();

const suggestion = ref('');
const generating = ref(false);

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

function normalizeToolName(rawToolName = '') {
  const normalized = String(rawToolName || '').trim().toLowerCase();
  if (!normalized) return '';
  const key = normalized.replace(/[\s_-]/g, '');
  const aliases = {
    rewriteworldview: 'rewrite_worldview',
  };
  return aliases[key] || normalized;
}

async function handleAdjust() {
  const projectName = projectStore.currentProject;
  if (!projectName) {
    bus.emit('toast', { type: 'error', message: '请先选择项目' });
    return;
  }

  const suggestionText = (suggestion.value || '').trim();
  if (!suggestionText) {
    bus.emit('toast', { type: 'warning', message: '请先输入修改意见' });
    return;
  }

  generating.value = true;
  let assistantText = '';
  let executed = false;
  const thinkParser = createThinkStreamParser();
  const task = createStreamingTask('world', {
    target: 'worldview',
    text: '正在重写世界观设定...',
    canCancel: true,
    autoStart: false,
    onCancel: () => {
      generating.value = false;
      bus.emit('toast', { type: 'info', message: '已取消世界观调整' });
    },
  });

  const message = [
    '你正在执行【工具箱：调整世界观】任务。',
    '请根据下方修改意见直接调用 rewrite_worldview 工具完成落盘。',
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
          assistantText += thinkParser.push(evt.text || '').display;
          return;
        }

        if (eventType === 'tool_intent_started' || eventType === 'tool_exec_started') {
          if (toolName === 'rewrite_worldview') {
            task.start('正在重写世界观设定...');
          }
          return;
        }

        if (eventType === 'tool_exec_finished' && toolName === 'rewrite_worldview') {
          executed = true;
          task.hide();
        }
      },
      onMalformedLine: (raw) => {
        assistantText += thinkParser.push(raw).display;
      }
    });

    assistantText += thinkParser.flush().display;

    if (task.aborted) return;

    if (executed) {
      bus.emit('lorebook-refresh-worldview');
      bus.emit('lorebook-refresh');
      bus.emit('toast', { type: 'success', message: '世界观设定已更新' });
      suggestion.value = '';
    } else {
      bus.emit('toast', { type: 'warning', message: assistantText.trim() || '本次未执行世界观重写工具，请调整描述后重试' });
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
.world-gen-panel {
  margin-top: 12px;
}

.world-gen-panel :deep(.n-card) {
  border: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
}
</style>
