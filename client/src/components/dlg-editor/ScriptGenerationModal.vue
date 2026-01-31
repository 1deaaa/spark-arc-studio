<template>
  <n-modal
    v-model:show="visible"
    :mask-closable="false"
    :close-on-esc="false"
    preset="card"
    class="script-gen-modal"
    :style="{ width: '600px' }"
  >
    <template #header>
      <div class="modal-header">
        <span>启动ScriptWritter</span>
        <svg v-if="status === 'running'" width="48" height="24" viewBox="0 0 48 24" class="pen-anim">
          <defs>
            <path id="inkPath" d="M2,14 C8,8 12,16 18,10 C22,6 26,14 32,12 C38,10 42,8 46,12" />
          </defs>
          
          <!-- 墨迹：使用不规则路径 -->
          <use href="#inkPath" fill="none" stroke="var(--spark-primary)" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="60" stroke-dashoffset="60">
            <animate attributeName="stroke-dashoffset" from="60" to="0" dur="1.8s" repeatCount="indefinite"/>
          </use>
          
          <!-- 详细钢笔：跟随同一路径 -->
          <g>
            <animateMotion dur="1.8s" repeatCount="indefinite">
              <mpath href="#inkPath"/>
            </animateMotion>
            
            <!-- 钢笔图形 -->
            <g transform="rotate(-30)">
               <!-- 笔杆 -->
               <path d="M-2,-18 L2,-18 L2,-4 L-2,-4 Z" fill="var(--spark-primary)"/>
               <!-- 装饰环 -->
               <rect x="-2.5" y="-6" width="5" height="1.5" rx="0.5" fill="var(--spark-primary)" opacity="0.8"/>
               <!-- 笔尖 (尖端在 0,0) -->
               <path d="M-2,-4 L2,-4 L0,0 Z" fill="var(--spark-primary)"/>
               <!-- 高光 -->
               <path d="M-0.5,-16 L-0.5,-8" stroke="white" stroke-width="0.8" opacity="0.4" stroke-linecap="round"/>
            </g>
          </g>
        </svg>
        <n-tag v-else-if="status === 'paused'" type="warning" size="small" class="status-tag">
          已暂停
        </n-tag>
        <n-tag v-else-if="status === 'complete'" type="info" size="small" class="status-tag">
          已完成
        </n-tag>
        <n-tag v-else-if="status === 'error'" type="error" size="small" class="status-tag">
          出错
        </n-tag>
      </div>
    </template>

    <div class="gen-content">
      <!-- 1. 设置区域 (未开始时显示) -->
      <div v-if="status === 'idle'" class="setup-panel">
        <n-alert type="warning" title="风险提示" class="warning-alert">
          <template #icon><n-icon :component="WarningOutline" /></template>
          零人工介入的连续生成可能会导致剧情逻辑误差的累计。强烈建议您选择“逐章生成”，并在每一章完成后进行审阅。
        </n-alert>

        <n-form label-placement="left" label-width="120px" class="setup-form">
          <n-form-item label="生成模式">
            <n-radio-group v-model:value="config.mode">
              <n-radio-button value="chapter_by_chapter" label="逐章生成 (推荐)" />
              <n-radio-button value="all" label="连续生成全本" />
            </n-radio-group>
          </n-form-item>
          
           <n-form-item label="起始章节" v-if="outlineNodes.length > 0">
             <n-select
               v-model:value="config.startChapterIndex"
               :options="chapterOptions"
               placeholder="选择开始位置"
             />
           </n-form-item>
        </n-form>

        <div class="start-actions">
           <n-button type="primary" size="large" @click="startGeneration">
             <template #icon><n-icon :component="PlayOutline" /></template>
             开始自动撰写
           </n-button>
        </div>
      </div>

      <!-- 2. 运行区域 (生成中/暂停/完成时显示) -->
      <div v-else class="running-panel">
        <!-- 进度总览 -->
        <div class="progress-section">
           <div class="current-task">
             <span class="label">当前进度:</span>
             <span class="value">{{ progressText }}</span>
           </div>
           <n-progress
             type="line"
             :percentage="progressPercentage"
             :indicator-placement="'inside'"
             processing
           />
        </div>

        <!-- 实时日志/预览 -->
        <div class="console-box" ref="consoleRef">
           <div v-for="(log, idx) in logs" :key="idx" class="log-item" :class="log.type">
             <span class="time">[{{ log.time }}]</span>
             <span class="msg">{{ log.message }}</span>
           </div>
           <div v-if="currentPreview" class="preview-block">
             <div class="preview-title">正在生成...</div>
             <div class="preview-line">{{ currentPreview }}</div>
           </div>
        </div>
        
        <!-- 控制栏 -->
        <div class="control-bar">
          <n-button v-if="status === 'running'" type="warning" @click="requestPause">
            <template #icon><n-icon :component="PauseOutline" /></template>
            暂停 / 停止
          </n-button>
          
          <template v-if="status === 'paused'">
             <div class="paused-hint">
               当前章节已完成生成。请检查 `{FinishedChapter}` 文件。
             </div>
             <n-button type="primary" @click="continueNextChapter">
               <template #icon><n-icon :component="PlaySkipForwardOutline" /></template>
               继续生成下一章
             </n-button>
             <n-button @click="closeModal">关闭窗口</n-button>
          </template>

          <n-button v-if="status === 'complete' || status === 'error'" @click="closeModal">
            关闭
          </n-button>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { NModal, NIcon, NTag, NSpin, NAlert, NForm, NFormItem, NRadioGroup, NRadioButton, NSelect, NButton, NProgress, useMessage } from 'naive-ui';
import { Sparkles, WarningOutline, PlayOutline, PauseOutline, PlaySkipForwardOutline } from '@vicons/ionicons5';
import { useProjectStore } from '../stores/projectStore';
import { fetchEventSource } from '@microsoft/fetch-event-source';

const props = defineProps({
  show: Boolean,
  outline: Object
});

const emit = defineEmits(['update:show', 'refresh-files']);

const projectStore = useProjectStore();
const message = useMessage();
const consoleRef = ref(null);

// State
const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
});

const status = ref('idle'); // idle, running, paused, complete, error
const logs = ref([]);
const currentPreview = ref('');
const progressText = ref('准备就绪');
const finishedChapterFilename = ref('');
const streamingStats = ref({ chars: 0, speed: 0, elapsed: 0 }); // 实时统计

// Config
const config = ref({
  mode: 'chapter_by_chapter',
  startChapterIndex: 0
});

// Computed properties for UI
const outlineNodes = computed(() => props.outline?.nodes || []);
const chapterOptions = computed(() => {
  return outlineNodes.value
    .filter(n => n.type === 'chapter')
    .map((c, idx) => ({
      label: `${c.title || ('第' + (c.chapter || idx+1) + '章')}`,
      value: idx
    }));
});

const totalChapters = computed(() => chapterOptions.value.length);
const currentChapterIdx = ref(0);
const progressPercentage = computed(() => {
  if (totalChapters.value === 0) return 0;
  // Simple approximation: (finished chapters / total) * 100
  // Fine-grained progress is hard without known scene counts per chapter
  const pct = Math.floor(((currentChapterIdx.value) / totalChapters.value) * 100);
  return Math.min(100, Math.max(0, pct));
});

// Methods
function addLog(msg, type = 'info') {
  logs.value.push({
    time: new Date().toLocaleTimeString(),
    message: msg,
    type
  });
  scrollToBottom();
}

function scrollToBottom() {
  nextTick(() => {
    if (consoleRef.value) {
      consoleRef.value.scrollTop = consoleRef.value.scrollHeight;
    }
  });
}

let controller = null;

async function startGeneration() {
  status.value = 'running';
  logs.value = []; // clear old logs? maybe keep? let's clear for fresh start
  addLog("开始生成任务...", "info");
  
  await runStream();
}

class RetriggerPrevented extends Error {}

async function runStream() {
  controller = new AbortController();
  const projectName = projectStore.currentProject;
  
  try {
    // Correct endpoint from our implementation plan
    // GET or POST? The server route is POST: @auto_write_router.post
    // fetchEventSource only supports POST if configured specifically, 
    // but the backend implementation `StreamingResponse` works with fetch.
    // Native EventSource does not support POST body.
    // We used `@microsoft/fetch-event-source` which supports POST.
    
    await fetchEventSource(`/api/outline/${encodeURIComponent(projectName)}/auto-write-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add auth token if needed, assume cookies handle it or add Authorization header
        // 'Authorization': `Bearer ${token}` 
      },
      body: JSON.stringify({
        mode: config.value.mode,
        start_chapter_index: config.value.startChapterIndex
      }),
      signal: controller.signal,
      openWhenHidden: true, // Keep connection alive when page is hidden/background

      
      onopen(response) {
        if (response.ok && response.headers.get('content-type').includes('text/event-stream')) {
          return; // everything's good
        } else if (response.status >= 400 && response.status < 500 && response.status !== 429) {
           throw new Error(`Failed to open stream: ${response.status}`);
        }
      },
      onmessage(msg) {
        if (!msg.data) return;
        try {
          const data = JSON.parse(msg.data);
          handleStreamEvent(data);
        } catch (e) {
          console.error("Parse error", e);
        }
      },
      onclose() {
        // Prevent auto-retry by throwing an error that we catch
        throw new RetriggerPrevented();
      },
      onerror(err) {
        if (controller && controller.signal.aborted) {
            // Aborted intentionally
            return; 
        }
        if (err instanceof RetriggerPrevented) {
            throw err; // rethrow to stop retries
        }
        addLog(`连接错误: ${err.message}`, 'error');
        status.value = 'error';
        throw err; // rethrow to stop retries
      }
    });
  } catch (err) {
    if (err instanceof RetriggerPrevented) {
        // Normal closure, do nothing
        return;
    }
    if (status.value !== 'paused' && status.value !== 'complete') { // don't log error if we paused intentionally or completed
        status.value = 'error';
        addLog(`任务终止: ${err.message}`, 'error');
    }
  }
}

function handleStreamEvent(data) {
  const oneLine = (val) => String(val ?? '').replace(/[\r\n]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
  switch (data.status) {
    case 'chapter_start':
      currentChapterIdx.value = data.chapter_index;
      progressText.value = `正在准备: ${data.chapter_title}`;
      addLog(`开始章节: ${data.chapter_title}`, 'info');
      break;
      
    case 'writing_scene':
      progressText.value = `正在撰写: ${data.chapter_title} - ${data.scene_title}`;
      // Do not spam logs for every scene update if scene updates are frequent
      // But writing_scene happens once per scene start
      addLog(`开始场景: ${data.scene_title}`, 'info');
      currentPreview.value = ''; // clear previous preview
      streamingStats.value = { chars: 0, speed: 0, elapsed: 0 }; // reset stats
      break;
    
    case 'streaming':
      // 实时更新预览和速度统计
      currentPreview.value = oneLine(`[${data.total_chars} 字 | ${data.speed} 字/秒 | ${data.elapsed}秒] ${data.preview}`);
      streamingStats.value = {
        chars: data.total_chars,
        speed: data.speed,
        elapsed: data.elapsed
      };
      scrollToBottom();
      break;
      
    case 'scene_completed':
      addLog(`✓ 场景完成: ${data.scene_title} (${data.total_chars || '?'}字, ${data.elapsed || '?'}秒, 平均${data.avg_speed || '?'}字/秒)`, 'success');
      currentPreview.value = oneLine(data.preview || '');
      break;
      
    case 'chapter_saved':
      addLog(`✅ 章节文件已保存: ${data.filename}`, 'success');
      finishedChapterFilename.value = data.filename;
      emit('refresh-files'); // Notify parent to refresh file tree
      break;
      
    case 'paused':
      if (controller) controller.abort(); // Close connection
      status.value = 'paused';
      // update next start index
      config.value.startChapterIndex = data.next_chapter_index;
      progressText.value = '任务已暂停 (完成章节节点)';
      addLog("任务已按计划暂停 (逐章模式)", 'warning');
      break;
      
    case 'complete':
      if (controller) controller.abort(); // Close connection
      status.value = 'complete';
      progressText.value = '全部任务完成';
      currentChapterIdx.value = totalChapters.value; // full bar
      addLog("🎉 全部生成任务已完成！", 'success');
      break;
      
    case 'error':
      status.value = 'error';
      addLog(`服务端错误: ${data.message}`, 'error');
      break;
  }
}


function requestPause() {
  if (controller) {
    controller.abort();
    controller = null;
  }
  status.value = 'paused';
  progressText.value = '任务已手动暂停';
  addLog("用户手动中断了生成", 'warning');
}

function continueNextChapter() {
  if (config.value.startChapterIndex >= totalChapters.value) {
    message.success("已经是最后一章了");
    status.value = 'complete';
    return;
  }
  startGeneration();
}

function closeModal() {
  if (status.value === 'running') {
    requestPause();
  }
  visible.value = false;
  // Reset state for next open if completed
  if (status.value === 'complete' || status.value === 'error') {
     status.value = 'idle';
  }
}
</script>

<style scoped>
.modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  font-weight: bold;
}

.gen-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding-top: 16px;
}

.setup-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.start-actions {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.running-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 16px;
  overflow: hidden;
}

.progress-section {
  background: var(--spark-bg-soft);
  padding: 16px;
  border-radius: 8px;
}

.current-task {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
}

.console-box {
  flex: 1;
  background: var(--spark-bg-secondary);
  color: var(--spark-text);
  padding: 12px;
  border-radius: 8px;
  font-family: var(--spark-mono);
  font-size: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid var(--spark-border);
  min-height: 300px;
  max-height: 50vh;
}

.log-item {
  display: flex;
  gap: 8px;
}

.log-item.info .msg { color: #a5d6ff; }
.log-item.success .msg { color: #8fdc9d; }
.log-item.warning .msg { color: #f9d868; }
.log-item.error .msg { color: #f87171; }

.log-item .time {
  color: #666;
  white-space: nowrap;
}

.preview-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #444;
  color: #888;
}

.preview-line {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.control-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--spark-border);
}

.paused-hint {
  flex: 1;
  display: flex;
  align-items: center;
  color: var(--spark-success);
  font-size: 13px;
}
</style>
