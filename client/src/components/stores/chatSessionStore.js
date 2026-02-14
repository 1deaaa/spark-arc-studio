import { defineStore } from 'pinia';
import { getChatHistory, sendChatMessageStream, clearChatHistory, deleteChatMessage, editChatMessageStream } from '@/services/chatService';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';

/**
 * 多窗口聊天会话管理 Store
 * 管理多个并行的 Agent 聊天窗口，强制同一 Agent 不能在多个窗口中同时选中。
 */
export const useChatSessionStore = defineStore('chatSession', {
    state: () => ({
        /** @type {Map<number, ChatSession>} 所有活跃会话 */
        sessions: {},
        /** 自增 ID */
        _nextId: 1,
        /** 全局上下文提供器 */
        _contextProvider: null,
    }),

    getters: {
        /** 返回所有会话的数组 */
        sessionList() {
            return Object.values(this.sessions);
        },

        /** 已被占用的 agent ID 集合 */
        occupiedAgentIds() {
            return new Set(Object.values(this.sessions).map(s => s.agentId));
        },

        /** 获取主会话（ID 最小的那个） */
        primarySession() {
            const ids = Object.keys(this.sessions).map(Number).sort((a, b) => a - b);
            return ids.length > 0 ? this.sessions[ids[0]] : null;
        },
    },

    actions: {
        /** 注册全局上下文提供器 */
        registerContextProvider(fn) {
            this._contextProvider = fn;
        },

        /** 检查 agent 是否已被占用 */
        isAgentOccupied(agentId) {
            return Object.values(this.sessions).some(s => s.agentId === agentId);
        },

        /** 获取未被占用的 agent 列表（基于传入的完整列表过滤） */
        getAvailableAgents(allAgents, excludeSessionId = null) {
            const occupied = new Set(
                Object.values(this.sessions)
                    .filter(s => s.id !== excludeSessionId)
                    .map(s => s.agentId)
            );
            return allAgents.filter(a => !occupied.has(a.value || a.key));
        },

        /**
         * 创建新会话
         * @param {string} agentId - 初始 agent ID
         * @returns {number} 新会话 ID
         */
        createSession(agentId = 'agent_director') {
            // 如果该 agent 已被占用，抛出异常
            if (this.isAgentOccupied(agentId)) {
                throw new Error(`Agent "${agentId}" 已在另一个窗口中使用`);
            }

            const id = this._nextId++;
            this.sessions[id] = {
                id,
                agentId,
                contextKey: 'global',
                expanded: true,
                history: [],
                loading: false,
                sending: false,
                toolCalling: false,
                toolName: '',
                toolProgressText: '',
                lastError: '',
            };
            return id;
        },

        /** 关闭并移除会话 */
        removeSession(sessionId) {
            delete this.sessions[sessionId];
        },

        /** 切换会话的 agent（强制互斥） */
        setSessionAgent(sessionId, agentId) {
            const session = this.sessions[sessionId];
            if (!session) return;

            // 检查该 agent 是否被其他会话占用
            const occupiedBy = Object.values(this.sessions).find(
                s => s.id !== sessionId && s.agentId === agentId
            );
            if (occupiedBy) {
                bus.emit('toast', { type: 'warning', message: `该 Agent 已在另一个窗口中使用` });
                return false;
            }

            session.agentId = agentId || 'agent_director';
            return true;
        },

        /** 设置会话的 contextKey */
        setSessionContextKey(sessionId, key) {
            const session = this.sessions[sessionId];
            if (session) {
                session.contextKey = (key || 'global').toString();
            }
        },

        /** 展开/收起会话面板 */
        setSessionExpanded(sessionId, v) {
            const session = this.sessions[sessionId];
            if (session) {
                session.expanded = !!v;
            }
        },

        /** 刷新会话历史 */
        async refreshSessionHistory(sessionId, limit = 80) {
            const session = this.sessions[sessionId];
            if (!session) return;

            const projectStore = useProjectStore();
            const projectName = projectStore.currentProject;
            if (!projectName) return;

            session.loading = true;
            session.lastError = '';
            try {
                session.history = await getChatHistory(projectName, session.agentId, session.contextKey, limit);
            } catch (e) {
                session.lastError = e?.message || '加载失败';
            } finally {
                session.loading = false;
            }
        },

        /** 发送消息到指定会话 */
        async sendSessionMessage(sessionId, message, targets) {
            const session = this.sessions[sessionId];
            if (!session) return;

            const projectStore = useProjectStore();
            const projectName = projectStore.currentProject;
            if (!projectName) throw new Error('未选择项目');
            const text = (message || '').trim();
            if (!text) return;

            session.sending = true;
            session.toolCalling = false;
            session.toolName = '';
            session.toolProgressText = '';

            try {
                // 动态获取当前上下文
                let activeContext = '';
                if (this._contextProvider) {
                    try {
                        activeContext = this._contextProvider();
                    } catch (e) {
                        console.warn('获取上下文失败', e);
                    }
                }

                // 乐观添加用户消息
                session.history = (session.history || []).concat([
                    { role: 'user', content: text, timestamp: Math.floor(Date.now() / 1000) }
                ]);

                // AI 回复占位
                const assistantMsg = { role: 'assistant', content: '', timestamp: Math.floor(Date.now() / 1000) };
                let assistantMsgAdded = false;

                const reader = await sendChatMessageStream(projectName, session.agentId, session.contextKey, text, targets, activeContext);
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
                    session.toolCalling = true;
                    session.toolName = normalizedToolName;
                    session.toolProgressText = progressText;
                    bus.emit('tool-call-start', { toolName: normalizedToolName, text: progressText, target, sessionId });

                    if (session.agentId === 'agent_lorebook' && isLorebookRewriteTool(normalizedToolName)) {
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
                    bus.emit('tool-call-end', { toolName, target, sessionId });

                    if (session.agentId === 'agent_lorebook' && isLorebookRewriteTool(toolName)) {
                        bus.emit('global-loading', { show: false, scope: 'world', target });
                        if (target === 'worldview') {
                            bus.emit('lorebook-refresh-worldview');
                        } else if (target === 'characters') {
                            bus.emit('lorebook-refresh-characters');
                        }
                        bus.emit('lorebook-refresh');
                    }

                    session.toolCalling = false;
                    session.toolName = '';
                    session.toolProgressText = '';
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

                    const trimmedChunk = displayChunk.trim();

                    if (!trimmedChunk) {
                        if (displayChunk && assistantMsgAdded) {
                            assistantMsg.content += displayChunk;
                            session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
                        }
                        continue;
                    }

                    if (!assistantMsgAdded) {
                        session.history = session.history.concat([assistantMsg]);
                        assistantMsgAdded = true;
                    }
                    assistantMsg.content += displayChunk;
                    session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
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
                                session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
                            }
                        } else {
                            if (!assistantMsgAdded) {
                                session.history = session.history.concat([assistantMsg]);
                                assistantMsgAdded = true;
                            }
                            assistantMsg.content += restChunk;
                            session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
                        }
                    }
                }

                if (currentToolName) {
                    onToolCallEnd(currentToolName);
                }

                if (!assistantMsg.content && session.agentId === 'agent_lorebook') {
                    if (!assistantMsgAdded) {
                        session.history = session.history.concat([assistantMsg]);
                    }
                    assistantMsg.content = '设定已更新。';
                    session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
                }

                // 从服务器同步持久化历史
                await this.refreshSessionHistory(sessionId, 80);
            } catch (e) {
                bus.emit('toast', { type: 'error', message: e?.message || '发送失败' });
                throw e;
            } finally {
                session.toolCalling = false;
                session.toolName = '';
                session.toolProgressText = '';
                bus.emit('global-loading', { show: false, scope: 'world' });
                session.sending = false;
            }
        },

        /** 清空会话历史 */
        async clearSession(sessionId) {
            const session = this.sessions[sessionId];
            if (!session) return;

            const projectStore = useProjectStore();
            const projectName = projectStore.currentProject;
            if (!projectName) return;
            await clearChatHistory(projectName, session.agentId, session.contextKey);
            session.history = [];
        },

        /** 删除会话中的单条消息 */
        async deleteSessionMessage(sessionId, messageId) {
            const session = this.sessions[sessionId];
            if (!session || !messageId) return;

            const projectStore = useProjectStore();
            const projectName = projectStore.currentProject;
            if (!projectName) return;

            try {
                await deleteChatMessage(projectName, messageId);
                session.history = session.history.filter(m => m.id !== messageId);
            } catch (e) {
                bus.emit('toast', { type: 'error', message: e?.message || '删除失败' });
            }
        },

        /** 编辑会话中的消息 */
        async editSessionMessage(sessionId, messageId, newContent) {
            const session = this.sessions[sessionId];
            if (!session || !messageId) return;

            const projectStore = useProjectStore();
            const projectName = projectStore.currentProject;
            if (!projectName) return;

            session.sending = true;
            try {
                const index = session.history.findIndex(m => m.id === messageId);
                if (index !== -1) {
                    const nextHistory = session.history.slice(0, index + 1);
                    nextHistory[index] = { ...nextHistory[index], content: newContent };
                    session.history = nextHistory;
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
                const reader = await editChatMessageStream(projectName, session.agentId, session.contextKey, messageId, newContent, activeContext);
                const decoder = new TextDecoder('utf-8');

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value, { stream: true });
                    if (!chunk) continue;

                    if (!assistantMsgAdded) {
                        session.history = session.history.concat([assistantMsg]);
                        assistantMsgAdded = true;
                    }
                    assistantMsg.content += chunk;
                    session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
                }

                const tailChunk = decoder.decode();
                if (tailChunk) {
                    if (!assistantMsgAdded) {
                        session.history = session.history.concat([assistantMsg]);
                        assistantMsgAdded = true;
                    }
                    assistantMsg.content += tailChunk;
                    session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
                }

                await this.refreshSessionHistory(sessionId, 80);
            } catch (e) {
                bus.emit('toast', { type: 'error', message: e?.message || '编辑失败' });
                throw e;
            } finally {
                session.sending = false;
            }
        },
    },
});
