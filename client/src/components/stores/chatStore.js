import { defineStore } from 'pinia';
import { getChatHistory, sendChatMessageStream, clearChatHistory, deleteChatMessage, editChatMessageStream } from '@/services/chatService';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';

export const useChatStore = defineStore('chat', {
  state: () => ({
    currentAgentId: 'agent_director',
    contextKey: 'global',
    expanded: false,
    history: [],
    loading: false,
    sending: false,
    toolCalling: false,
    toolName: '',
    toolProgressText: '',
    lastError: '',
    _contextProvider: null,
  }),

  actions: {
    registerContextProvider(fn) {
      this._contextProvider = fn;
    },

    setExpanded(v) {
      this.expanded = !!v;
    },

    toggleExpanded() {
      this.expanded = !this.expanded;
    },

    setAgent(agentId) {
      this.currentAgentId = agentId || 'agent_director';
    },

    setContextKey(key) {
      this.contextKey = (key || 'global').toString();
    },

    async refreshHistory(limit = 50) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      this.loading = true;
      this.lastError = '';
      try {
        this.history = await getChatHistory(projectName, this.currentAgentId, this.contextKey, limit);
      } catch (e) {
        this.lastError = e?.message || '加载失败';
      } finally {
        this.loading = false;
      }
    },

    async send(message, targets) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) throw new Error('未选择项目');
      const text = (message || '').trim();
      if (!text) return;

      this.sending = true;
      this.toolCalling = false;
      this.toolName = '';
      this.toolProgressText = '';
      try {
        // 动态获取当前上下文（比如整个场景的文本）
        let activeContext = '';
        if (this._contextProvider) {
          try {
            activeContext = this._contextProvider();
          } catch (e) {
            console.warn('获取上下文失败', e);
          }
        }

        // Optimistically add user message
        this.history = (this.history || []).concat([{ role: 'user', content: text, timestamp: Math.floor(Date.now() / 1000) }]);

        // Placeholder assistant message - 延迟添加直到收到实际内容
        const assistantMsg = { role: 'assistant', content: '', timestamp: Math.floor(Date.now() / 1000) };
        let assistantMsgAdded = false;

        const reader = await sendChatMessageStream(projectName, this.currentAgentId, this.contextKey, text, targets, activeContext);
        const decoder = new TextDecoder('utf-8');
        const STREAM_START = '[[WORLDVIEW_STREAM_START]]';
        const STREAM_END = '[[WORLDVIEW_STREAM_END]]';
        const TOOL_CALL_START_REGEX = /^<!--\s*(?:TOOL_CALL_START|TOOLCALLSTART):([\w-]+)(?::([\s\S]*?))?\s*-->$/i;
        const TOOL_CALL_END_REGEX = /^<!--\s*(?:TOOL_CALL_END|TOOLCALLEND)(?::([\w-]+))?\s*-->$/i;
        const TOOL_CALL_START_PREFIXES = ['<!-- TOOL_CALL_START:', '<!-- TOOLCALLSTART:'];
        const TOOL_CALL_END_PREFIXES = ['<!-- TOOL_CALL_END', '<!-- TOOLCALLEND'];

        let isWorldviewStreaming = false;
        let currentToolName = '';
        let streamBuffer = '';

        const normalizeToolName = (rawToolName = '') => {
          const normalized = String(rawToolName || '').trim().toLowerCase();
          if (!normalized) return '';
          const key = normalized.replace(/[\s_-]/g, '');
          const aliases = {
            rewriteworldview: 'rewrite_worldview',
            rewriteallcharacters: 'rewrite_all_characters',
            rewritecharacters: 'rewrite_all_characters',
            rewritecharacter: 'update_character',
            updatecharacter: 'update_character',
          };
          return aliases[key] || normalized;
        };

        const getToolProgressText = (toolName, fallbackText = '') => {
          if (fallbackText && fallbackText.trim()) return fallbackText.trim();
          const mapping = {
            rewrite_worldview: '正在重写世界观设定...',
            rewrite_all_characters: '正在重写角色设定...',
            update_character: '正在更新角色设定...',
          };
          return mapping[toolName] || `正在执行工具 ${toolName} ...`;
        };

        const isLorebookRewriteTool = (toolName) => {
          return toolName === 'rewrite_worldview' || toolName === 'rewrite_all_characters';
        };

        const getLorebookRefreshTarget = (toolName) => {
          if (toolName === 'rewrite_worldview') return 'worldview';
          if (toolName === 'rewrite_all_characters' || toolName === 'update_character') return 'characters';
          return '';
        };

        const findNextMarkerStart = (text) => {
          const indexes = [
            text.indexOf(STREAM_START),
            text.indexOf(STREAM_END),
            text.indexOf('<!--'),
          ].filter(i => i >= 0);
          if (indexes.length === 0) return -1;
          return Math.min(...indexes);
        };

        const onToolCallStart = (toolName, progressText) => {
          if (!toolName) return;
          const normalizedToolName = normalizeToolName(toolName);
          currentToolName = normalizedToolName;
          const target = getLorebookRefreshTarget(normalizedToolName);
          this.toolCalling = true;
          this.toolName = normalizedToolName;
          this.toolProgressText = progressText;
          bus.emit('tool-call-start', { toolName: normalizedToolName, text: progressText, target });

          if (this.currentAgentId === 'agent_lorebook' && isLorebookRewriteTool(normalizedToolName)) {
            bus.emit('global-loading', {
              show: true,
              text: progressText,
              canCancel: false,
              scope: 'world',
              target,
            });
          }
        };

        const onToolCallEnd = (endedToolName) => {
          const toolName = normalizeToolName(endedToolName || currentToolName);
          const target = getLorebookRefreshTarget(toolName);
          bus.emit('tool-call-end', { toolName, target });

          if (this.currentAgentId === 'agent_lorebook' && isLorebookRewriteTool(toolName)) {
            bus.emit('global-loading', { show: false, scope: 'world', target });
            if (target === 'worldview') {
              bus.emit('lorebook-refresh-worldview');
            } else if (target === 'characters') {
              bus.emit('lorebook-refresh-characters');
            }
            bus.emit('lorebook-refresh');
          }

          this.toolCalling = false;
          this.toolName = '';
          this.toolProgressText = '';
          currentToolName = '';
        };

        const processMarkers = (incomingText, flush = false) => {
          if (incomingText) {
            streamBuffer += incomingText;
          }

          let visibleOutput = '';

          while (streamBuffer.length > 0) {
            const markerStart = findNextMarkerStart(streamBuffer);

            if (markerStart < 0) {
              if (flush) {
                visibleOutput += streamBuffer;
                streamBuffer = '';
              } else {
                const keepTail = 128;
                if (streamBuffer.length > keepTail) {
                  visibleOutput += streamBuffer.slice(0, streamBuffer.length - keepTail);
                  streamBuffer = streamBuffer.slice(-keepTail);
                }
              }
              break;
            }

            if (markerStart > 0) {
              visibleOutput += streamBuffer.slice(0, markerStart);
              streamBuffer = streamBuffer.slice(markerStart);
              continue;
            }

            if (streamBuffer.startsWith(STREAM_START)) {
              isWorldviewStreaming = true;
              bus.emit('worldview-stream-start');
              streamBuffer = streamBuffer.slice(STREAM_START.length);
              continue;
            }

            if (streamBuffer.startsWith(STREAM_END)) {
              isWorldviewStreaming = false;
              bus.emit('worldview-stream-end');
              streamBuffer = streamBuffer.slice(STREAM_END.length);
              continue;
            }

            const isToolCallStartMarker = TOOL_CALL_START_PREFIXES.some(prefix => streamBuffer.startsWith(prefix));
            const isToolCallEndMarker = TOOL_CALL_END_PREFIXES.some(prefix => streamBuffer.startsWith(prefix));

            if (isToolCallStartMarker || isToolCallEndMarker) {
              const commentEnd = streamBuffer.indexOf('-->');
              if (commentEnd < 0) {
                if (flush) {
                  streamBuffer = '';
                }
                break;
              }

              const markerText = streamBuffer.slice(0, commentEnd + 3);
              const startMatch = markerText.match(TOOL_CALL_START_REGEX);
              if (startMatch) {
                const toolName = normalizeToolName(startMatch[1] || '');
                const progressText = getToolProgressText(toolName, startMatch[2] || '');
                onToolCallStart(toolName, progressText);
              } else {
                const endMatch = markerText.match(TOOL_CALL_END_REGEX);
                if (endMatch) {
                  onToolCallEnd(endMatch[1] || currentToolName);
                }
              }

              streamBuffer = streamBuffer.slice(commentEnd + 3);
              continue;
            }

            visibleOutput += streamBuffer[0];
            streamBuffer = streamBuffer.slice(1);
          }

          return visibleOutput;
        };

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;
          const displayChunk = processMarkers(chunk, false);

          if (!displayChunk) continue;

          if (isWorldviewStreaming) {
            if (displayChunk) {
              bus.emit('worldview-stream-chunk', { text: displayChunk });
            }
            continue;
          }

          // 去除所有标记后判断是否有实际可见内容
          // 跳过只包含空白、换行或被标记占用的 chunk
          const trimmedChunk = displayChunk.trim();

          // 如果 chunk 被完全消耗（只有标记），跳过
          if (!trimmedChunk) {
            // 如果已经有消息框且原始 chunk 不为空（包含换行等），保留
            if (displayChunk && assistantMsgAdded) {
              assistantMsg.content += displayChunk;
              this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
            }
            continue;
          }

          // 有实际可见内容，添加消息框
          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
            assistantMsgAdded = true;
          }
          assistantMsg.content += displayChunk;
          // 强制触发 Vue 响应式更新：替换数组最后一项以实时渲染
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
        }

        const restChunk = processMarkers('', true);
        if (restChunk) {
          if (isWorldviewStreaming) {
            bus.emit('worldview-stream-chunk', { text: restChunk });
          } else {
            const trimmedRest = restChunk.trim();
            if (!trimmedRest) {
              if (assistantMsgAdded) {
                assistantMsg.content += restChunk;
                this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
              }
            } else {
              if (!assistantMsgAdded) {
                this.history = this.history.concat([assistantMsg]);
                assistantMsgAdded = true;
              }
              assistantMsg.content += restChunk;
              this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
            }
          }
        }

        if (currentToolName) {
          onToolCallEnd(currentToolName);
        }

        if (!assistantMsg.content && this.currentAgentId === 'agent_lorebook') {
          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
          }
          assistantMsg.content = '设定已更新。';
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
        }

        // Sync persisted history from server
        await this.refreshHistory(80);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '发送失败' });
        throw e;
      } finally {
        this.toolCalling = false;
        this.toolName = '';
        this.toolProgressText = '';
        bus.emit('global-loading', { show: false, scope: 'world' });
        this.sending = false;
      }
    },

    async clear() {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;
      await clearChatHistory(projectName, this.currentAgentId, this.contextKey);
      this.history = [];
    },

    async deleteMessage(messageId) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName || !messageId) return;

      try {
        await deleteChatMessage(projectName, messageId);
        this.history = this.history.filter(m => m.id !== messageId);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '删除失败' });
      }
    },

    async editMessage(messageId, newContent) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName || !messageId) return;

      this.sending = true;
      try {
        // 立即在本地清空该消息之后的回复，提供即时反馈
        const index = this.history.findIndex(m => m.id === messageId);
        if (index !== -1) {
          const nextHistory = this.history.slice(0, index + 1);
          nextHistory[index] = { ...nextHistory[index], content: newContent };
          this.history = nextHistory;
        }

        let activeContext = '';
        if (this._contextProvider) {
          try {
            activeContext = this._contextProvider();
          } catch (e) {
            console.warn('获取上下文失败', e);
          }
        }

        const assistantMsg = { role: 'assistant', content: '', timestamp: Math.floor(Date.now() / 1000) };
        let assistantMsgAdded = false;
        const reader = await editChatMessageStream(projectName, this.currentAgentId, this.contextKey, messageId, newContent, activeContext);
        const decoder = new TextDecoder('utf-8');

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;

          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
            assistantMsgAdded = true;
          }
          assistantMsg.content += chunk;
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
        }

        const tailChunk = decoder.decode();
        if (tailChunk) {
          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
            assistantMsgAdded = true;
          }
          assistantMsg.content += tailChunk;
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
        }

        // Sync persisted history from server (which should have deleted future messages and added a new reply)
        await this.refreshHistory(80);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '编辑失败' });
        throw e;
      } finally {
        this.sending = false;
      }
    },
  }
});
