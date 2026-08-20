<template>
  <div class="container">
    <HeaderToolbar
      :username="username"
      @open-settings="openSettings"
      @logout="onLogout"
      @open-version-manager="openVersionManager"
    />

    <main>
      <ActivityBar @open-settings="openSettings" />

      <div class="workspace-area">
        <transition name="spark-view" mode="out-in">
          <keep-alive>
            <component :is="activeComponent" :key="viewStore.currentView" :projectId="projectStore.currentProject" />
          </keep-alive>
        </transition>

        <div v-show="viewStore.currentView === 'production'" class="production-shell">
          <div class="production-layout">
            <div class="panel sidebar-panel" :style="{ width: sidebarWidth + 'px' }">
              <div class="sidebar-section file-section">
                <div class="file-section-header">
                  <span class="file-section-title">{{ t('views.scriptWriter.desktop.workspaceManager') }}</span>
                  <n-dropdown
                    v-if="isNovelWorkspace"
                    trigger="click"
                    :options="submissionExportOptions"
                    :disabled="!projectStore.currentProject || exportingSubmission"
                    @select="handleSubmissionExport"
                  >
                    <n-button
                      class="submission-platform-button"
                      secondary
                      size="small"
                      :loading="exportingSubmission"
                      :disabled="!projectStore.currentProject"
                    >
                      <template #icon>
                        <n-icon>
                          <Send />
                        </n-icon>
                      </template>
                      {{ t('components.novelEditor.submissionExport.button') }}
                    </n-button>
                  </n-dropdown>
                </div>
                <FileTree :key="workspaceMode" />
              </div>
            </div>

            <div class="resizer" data-resize="sidebar" @mousedown="handleMouseDown"></div>

            <div class="panel center-panel" style="position: relative;">
              <div class="center-panel-header">
                <h2 v-if="settingsVisible">{{ t('views.scriptWriter.desktop.settingEditor') }}</h2>
                <h2 v-else-if="!isNovelWorkspace">{{ t('views.scriptWriter.desktop.dialogueTree') }}</h2>
                <h2 v-else>{{ t('views.scriptWriter.desktop.modeNovel') }}</h2>
                <OnboardingHelpButton v-if="!settingsVisible" scene-id="page-production" />
              </div>

              <Transition name="workspace-mode" mode="out-in">
                <LorebookEditor v-if="settingsVisible" key="settings" :visible="true" @close="settingsVisible = false" />
                <NovelReader v-else-if="isNovelWorkspace" key="novel-editor" :content="typeof sceneStore.scriptData === 'string' ? sceneStore.scriptData : ''" />
                <DialogueTree v-else key="dialogue-tree" />
              </Transition>

              <GlobalLoading scope="production" />
            </div>

            <Transition name="inspector-slide">
              <div v-if="showInspectorPanel" class="resizer" data-resize="center" @mousedown="handleMouseDown"></div>
            </Transition>

            <Transition name="inspector-slide">
              <div v-show="showInspectorPanel" class="panel inspector-panel" :style="{ width: inspectorWidth + 'px' }">
                <template v-if="!settingsVisible">
                  <NodeEditor key="node-editor" />
                </template>
                <div v-else class="settings-right-panel">
                  <AiSettingsPanel :visible="true" />
                  <CharacterGeneratorPanel :visible="true" />
                </div>
              </div>
            </Transition>

            <template v-if="aiSidebarVisible">
              <div class="resizer" data-resize="inspector" @mousedown="handleMouseDown"></div>
              <div class="panel ai-sidebar" :style="{ width: aiSidebarWidth + 'px' }">
                <AiPanel />
              </div>
            </template>

            <!-- 右侧 Docked 智能对话边栏（PC 编剧面板自动停靠） -->
            <template v-if="chatSidebarVisible">
              <div class="resizer" data-resize="chat-sidebar" @mousedown="handleMouseDown"></div>
              <div class="panel chat-docked-sidebar" :style="{ width: chatSidebarWidth + 'px' }">
                <ChatPanel
                  ref="dockedChatPanelRef"
                  :agent-id="chat.currentAgentId"
                  :agent-options="agentOptions"
                  :allow-agent-switch-while-sending="true"
                  :history="chat.history"
                  :loading="chat.loading"
                  :last-error="chat.lastError"
                  :sending="chat.sending"
                  :thinking-seconds="thinkingSeconds"
                  :tool-calling="chat.toolCalling"
                  :tool-name="chat.toolName"
                  :tool-progress-text="chat.toolProgressText"
                  :retry-attempt="chat.retryAttempt"
                  :retry-mode="chat.retryMode"
                  :retry-max-retries="chat.retryMaxRetries"
                  :retry-error-summary="chat.retryErrorSummary"
                  :context-token-count="chat.contextTokenCount"
                  :context-token-usage="chat.contextTokenUsage"
                  :context-window-stats="chat.contextWindowStats"
                  loading-target="chat-primary"
                  :editing-message-id="editingMessageId"
                  :editing-content="editingContent"
                  :draft="draft"
                  @update:agent-id="onAgentChanged"
                  @update:draft="draft = $event"
                  @update:editing-content="editingContent = $event"
                  @clear="clear"
                  @compact-context="compactContext"
                  @send="send"
                  @stop="stop"
                  @draft-keydown="onDraftKeydown"
                  @start-edit="startEdit"
                  @cancel-edit="cancelEdit"
                  @save-edit="saveEdit"
                  @edit-keydown="onEditKeydown"
                  @delete-msg="deleteMsg"
                  @retry="retryMsg"
                >
                  <template #input-prefix>
                    <ChatFileImportButton :session-id="primarySessionId" :agent-id="chat.currentAgentId" />
                    <AiSettingsPanel :visible="true" :compact="true" :agent-name="chat.currentAgentId" placement="top-start" trigger="icon" />
                  </template>
                  <!-- 在工作区打开按钮 -->
                  <template #header-actions>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button size="tiny" @click="openInWorkspace" class="btn-action-clear" circle quaternary style="margin-left: 2px;">
                          <template #icon>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                              <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                            </svg>
                          </template>
                        </n-button>
                      </template>
                      {{ t('components.chatPanel.openInWorkspace') }}
                    </n-tooltip>
                  </template>
                  <!-- 收起边栏按钮 -->
                  <template #header-right>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button quaternary circle size="small" @click="toggleChatSidebar">
                          <template #icon>
                            <n-icon :size="16"><PanelRightClose /></n-icon>
                          </template>
                        </n-button>
                      </template>
                      {{ t('views.scriptWriter.desktop.collapseChatSidebar') || '收起智能助手' }}
                    </n-tooltip>
                  </template>
                </ChatPanel>
              </div>
            </template>

            <!-- 边栏折叠时停靠在右侧边缘的微光条 -->
            <div
              v-else
              class="chat-docked-collapsed-strip"
              @click="toggleChatSidebar"
              :title="t('views.scriptWriter.desktop.expandChatSidebar') || '展开智能助手'"
            >
              <div class="collapsed-strip-glow"></div>
              <div class="collapsed-strip-icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path class="spark-main" d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
                  <path class="spark-sub-1" d="M19 2L20 5L23 6L20 7L19 10L18 7L15 6L18 5L19 2Z" fill="currentColor" />
                </svg>
              </div>
              <span class="collapsed-strip-text">{{ t('views.scriptWriter.desktop.aiAssistant') || '智能助手' }}</span>
            </div>
          </div>
        </div>
      </div>

      <n-modal v-model:show="versionManagerVisible" preset="card" :title="t('views.scriptWriter.desktop.versionManager')" style="width: 800px; max-height: 90vh;">
        <VersionManager :projectId="projectStore.currentProject || undefined" :content-format="workspaceMode" hide-title />
      </n-modal>

      <GlobalChatFloat />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { NButton, NDropdown, NIcon, NModal, NTooltip, type DropdownOption } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { useOnboarding } from '../../onboarding';
import VersionManager from '../../components/dlg-editor/VersionManager.vue';
import HeaderToolbar from '../../components/layouts/desktop/HeaderToolbar.vue';
import FileTree from '../../components/file-explorer/FileTree.vue';
import BlueprintView from '../Blueprint/BlueprintIndex.vue';
import DialogueTree from '../../components/dlg-editor/DialogueTree.vue';
import NovelReader from '../../components/dlg-editor/NovelReader.vue';
import NodeEditor from '../../components/dlg-editor/NodeEditor.vue';
import AiPanel from '../../components/dlg-editor/AiPanel.vue';
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
import CharacterGeneratorPanel from '../../components/lorebook/CharacterGeneratorPanel.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import GlobalChatFloat from '../../components/chat/GlobalChatFloat.vue';
import ChatPanel from '../../components/chat/ChatPanel.vue';
import ChatFileImportButton from '../../components/chat/ChatFileImportButton.vue';
import ActivityBar from '../../components/layouts/desktop/ActivityBar.vue';
import OnboardingHelpButton from '../../onboarding/components/OnboardingHelpButton.vue';

// 这里的 View 引用改为新的分发器路径
import WorldView from '../World/WorldIndex.vue';
import CharactersView from '../Characters/CharactersIndex.vue';
import SynopsisView from '../Synopsis/SynopsisIndex.vue';
import StructureView from '../Structure/StructureIndex.vue';
import StyleView from '../Style/StyleIndex.vue';
import EngineView from '../Engine/EngineIndex.vue';
import SettingsView from '../Settings/SettingsIndex.vue';
import DashboardView from '../Dashboard/DashboardIndex.vue';
import ChatDesktopView from '../ChatDesktop/ChatDesktopIndex.vue';

import bus from '../../eventBus';
import { useResizer } from '../../hooks/useResizer';
import { useScriptWriterLogic } from '../../composables/useScriptWriterLogic';
import { useSceneStore } from '../../components/stores/sceneStore';
import { useChatStore } from '../../components/stores/chatStore';
import { useChatActions } from '../../composables/useChatActions';
import { useAgentRegistry } from '../../composables/useAgentRegistry';
import { Send, PanelRightClose } from '@lucide/vue';
import { shouldShowProductionInspector } from './productionInspector';
import {
  NOVEL_SUBMISSION_PLATFORMS,
  downloadNovelSubmissionExport,
  type NovelSubmissionPlatform,
} from '../../services/storyService';

const { t } = useI18n();
const sceneStore = useSceneStore();
const { sidebarWidth, inspectorWidth, aiSidebarWidth, chatSidebarWidth, handleMouseDown } = useResizer();
const {
  viewStore,
  projectStore,
  username,
  settingsVisible,
  versionManagerVisible,
  aiSidebarVisible,
  openSettings,
  onLogout
} = useScriptWriterLogic();

// ==================== 右侧智能编剧对话边栏 ====================
const chat = useChatStore();
const { registry: agentRegistry, load: loadAgentRegistry } = useAgentRegistry();
const dockedChatPanelRef = ref<any>(null);
const dockedListRef = computed(() => dockedChatPanelRef.value?.listRef);

const chatActions = useChatActions({
  getSending: () => chat.sending,
  getHistory: () => chat.history,
  send: (msg) => chat.send(msg),
  stop: () => chat.cancel(),
  clear: () => chat.clear(),
  editMessage: (id, content) => chat.editMessage(id, content),
  deleteMessage: (id) => chat.deleteMessage(id),
}, {
  listRef: dockedListRef,
  getEditScopeKey: () => `${chat.currentAgentId || ''}::${chat.contextKey || ''}`,
});

const {
  draft, editingMessageId, editingContent, thinkingSeconds,
  onDraftKeydown, send, stop, startEdit, cancelEdit,
  onEditKeydown, saveEdit, deleteMsg, retryMsg, scrollToBottom
} = chatActions;

async function clear() {
  await chatActions.clear();
}

async function compactContext() {
  if (chat.sending) return;
  await chat.compactContext();
}

const primarySessionId = computed(() => chat.primarySession?.id ?? null);

const agentOptions = computed(() =>
  agentRegistry.value
    .filter(a => a.visibleInChat !== false)
    .map(a => ({
      label: a.name || a.key,
      value: a.key,
    }))
);

function onAgentChanged(agentId: string) {
  chat.setAgent(agentId);
}

function openInWorkspace() {
  viewStore.openChatView(chat.currentAgentId);
}

const CHAT_SIDEBAR_STORAGE_KEY = 'spark_chat_sidebar_visible_v1';
const chatSidebarVisible = ref(true);

function loadChatSidebarVisible() {
  try {
    const saved = localStorage.getItem(CHAT_SIDEBAR_STORAGE_KEY);
    if (saved !== null) {
      chatSidebarVisible.value = saved === 'true';
    }
  } catch {}
}

function toggleChatSidebar() {
  chatSidebarVisible.value = !chatSidebarVisible.value;
  if (chatSidebarVisible.value) {
    // 停靠面板重新显示时，确保历史消息从最新内容开始展示。
    nextTick(() => scrollToBottom(true));
  }
  try {
    localStorage.setItem(CHAT_SIDEBAR_STORAGE_KEY, String(chatSidebarVisible.value));
  } catch {}
}

// 首次进入桌面工作台时触发引导（等待登录后检查完成）
const { triggerIfFirst } = useOnboarding();
const onPostLoginReady = () => {
  nextTick(() => triggerIfFirst('desktop-workspace'));
};
onMounted(() => {
  loadChatSidebarVisible();
  loadAgentRegistry();
  bus.on('post-login-ready', onPostLoginReady);
  // 如果 App.vue 已经发过 post-login-ready（竞态：子组件晚于 App mount），直接触发
  if ((bus as any).postLoginReadySent) onPostLoginReady();
});
onUnmounted(() => {
  bus.off('post-login-ready', onPostLoginReady);
});

function openVersionManager() {
  versionManagerVisible.value = true;
}

const workspaceMode = computed(() => sceneStore.workspaceMode || 'script');

const isNovelWorkspace = computed(() => workspaceMode.value === 'novel');
const showInspectorPanel = computed(() => shouldShowProductionInspector({
  isNovelWorkspace: isNovelWorkspace.value,
  settingsVisible: settingsVisible.value,
  hasOpenScriptFile: !!sceneStore.currentFilePath,
  hasCurrentScene: !!sceneStore.currentScene,
  selectionType: sceneStore.selectionType,
}));
const exportingSubmission = ref(false);
const submissionExportOptions = computed<DropdownOption[]>(() => (
  NOVEL_SUBMISSION_PLATFORMS.map(platform => ({
    key: platform,
    label: t(`components.novelEditor.submissionExport.platforms.${platform}`),
    icon: () => h(NIcon, null, { default: () => h(Send) }),
  }))
));

async function handleSubmissionExport(key: string | number) {
  if (exportingSubmission.value) return;
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('components.novelEditor.submissionExport.noProject') });
    return;
  }

  exportingSubmission.value = true;
  try {
    if (sceneStore.workspaceMode === 'novel') {
      await sceneStore._saveStory();
    }
    await downloadNovelSubmissionExport(projectStore.currentProject, key as NovelSubmissionPlatform);
    bus.emit('toast', { type: 'success', message: t('components.novelEditor.submissionExport.success') });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    bus.emit('toast', {
      type: 'error',
      message: `${t('components.novelEditor.submissionExport.failed')}: ${errorMessage}`,
    });
  } finally {
    exportingSubmission.value = false;
  }
}

const activeComponent = computed(() => {
  switch (viewStore.currentView) {
    case 'world': return WorldView;
    case 'characters': return CharactersView;
    case 'synopsis': return SynopsisView;
    case 'structure': return StructureView;
    case 'style': return StyleView;
    case 'engine': return EngineView;
    case 'blueprint': return BlueprintView;
    case 'settings': return SettingsView;
    case 'dashboard': return DashboardView;
    case 'chat': return ChatDesktopView;
    default: return null;
  }
});
</script>

<style scoped>
.container {
  height: 100vh;
  width: 100%;
  max-width: none;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.workspace-area {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  overflow: hidden;
  position: relative;
}

.production-shell {
  display: flex;
  flex-direction: column;
  flex: 1;
  width: 100%;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: var(--spark-bg);
}

.production-layout {
  display: flex;
  flex: 1;
  width: 100%;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.sidebar-panel {
  width: 250px;
  min-width: 0;
  max-width: 400px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color-modal);
  border-right: 1px solid var(--n-border-color);
}

.sidebar-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 8px 8px 16px;
  background: var(--spark-panel-header-bg);
  border-bottom: 1px solid var(--spark-border);
  flex-shrink: 0;
}

.file-section-title {
  flex: 1 1 auto;
  min-width: 0;
  font-size: var(--spark-fs-base);
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.submission-platform-button {
  flex: 0 1 auto;
  max-width: 100%;
}

.submission-platform-button :deep(.n-button__content) {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sidebar-divider {
  height: 1px;
  background-color: var(--n-border-color);
  margin: 4px 0;
}

.center-panel {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color);
}

.center-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--spark-panel-header-bg);
  border-bottom: 1px solid var(--spark-border);
  flex-shrink: 0;
  position: relative;
}

.inspector-panel {
  width: 300px;
  min-width: 0;
  max-width: 600px;
  flex: 0 0 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color-modal);
  border-left: 1px solid var(--n-border-color);
}

.ai-sidebar {
  width: 350px;
  min-width: 0;
  max-width: 800px;
  flex: 0 0 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--n-color-modal);
  border-left: 1px solid var(--n-border-color);
}

.chat-docked-sidebar {
  width: 380px;
  min-width: 0;
  max-width: 800px;
  flex: 0 0 auto;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--n-color-modal);
  border-left: 1px solid var(--n-border-color);
  position: relative;
}

.chat-docked-collapsed-strip {
  width: 36px;
  flex: 0 0 36px;
  height: 100%;
  background: var(--spark-panel-header-bg);
  border-left: 1px solid var(--spark-border);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  user-select: none;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.chat-docked-collapsed-strip:hover {
  background: color-mix(in srgb, var(--spark-panel-header-bg), var(--spark-primary) 8%);
  border-left-color: var(--spark-primary-muted);
  box-shadow: inset 2px 0 8px rgba(var(--spark-primary-rgb), 0.15);
}

.collapsed-strip-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--spark-primary);
  margin-bottom: 12px;
  transition: transform 0.3s ease;
}

.chat-docked-collapsed-strip:hover .collapsed-strip-icon {
  transform: scale(1.15) rotate(5deg);
}

.collapsed-strip-icon svg {
  width: 100%;
  height: 100%;
}

.collapsed-strip-text {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: 3px;
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  color: var(--spark-text-muted);
  transition: color 0.2s ease;
}

.chat-docked-collapsed-strip:hover .collapsed-strip-text {
  color: var(--spark-primary);
}

.settings-right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding: 12px;
}

.resizer {
  width: 4px;
  flex-shrink: 0;
  background: transparent;
  cursor: col-resize;
  z-index: 10;
  transition: background 0.2s;
}

.resizer:hover {
  background: var(--spark-primary);
}

h2 {
  font-size: var(--spark-fs-base);
  padding: 0;
  margin: 0;
}

.workspace-mode-enter-from,
.workspace-mode-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.995);
}
.workspace-mode-enter-active,
.workspace-mode-leave-active {
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(.4,0,.2,1);
}
.workspace-mode-enter-to,
.workspace-mode-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.inspector-slide-enter-from {
  opacity: 0;
  transform: translateX(18px);
}
.inspector-slide-leave-to {
  opacity: 0;
  transform: translateX(18px);
}
.inspector-slide-enter-active,
.inspector-slide-leave-active {
  transition: opacity 0.24s ease, transform 0.24s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
}
.inspector-slide-enter-to,
.inspector-slide-leave-from {
  opacity: 1;
  transform: translateX(0);
}

@media (max-width: 1520px) {
  .resizer {
    width: 3px;
  }
}

@media (max-width: 1280px) {
  h2 {
    font-size: var(--spark-fs-sm);
    padding: 8px 12px;
  }

  .sidebar-panel {
    max-width: 260px;
  }

  .inspector-panel {
    max-width: 320px;
  }

  .ai-sidebar {
    max-width: 340px;
  }

  .chat-docked-sidebar {
    max-width: 400px;
  }

  .settings-right-panel {
    padding: 10px;
    gap: 12px;
  }
}
</style>
