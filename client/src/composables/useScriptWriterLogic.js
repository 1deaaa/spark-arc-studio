
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import bus from '../eventBus';
import { useViewStore } from '../components/stores/viewStore';
import { useSceneStore } from '../components/stores/sceneStore';
import { useProjectStore } from '../components/stores/projectStore';
import { useFileStore } from '../components/stores/fileStore';
import { useChatStore } from '../components/stores/chatStore';
import { getUserInfo } from '../services/api';
import { serializeToArc } from '../services/arcParser';

export function useScriptWriterLogic() {
    const route = useRoute();
    const router = useRouter();
    const viewStore = useViewStore();
    const sceneStore = useSceneStore();
    const projectStore = useProjectStore();
    const fileStore = useFileStore();
    const chatStore = useChatStore();

    const urlHydrated = ref(false);
    const isRestoringUrl = ref(false);
    const isSyncingUrl = ref(false);
    const settingsVisible = ref(false);
    const versionManagerVisible = ref(false);
    const aiSidebarVisible = ref(true);
    const username = ref('');
    const autoSaveEnabled = ref(localStorage.getItem('autoSaveEnabled') === 'true');
    const saveHintVisible = ref(false);

    function safeDecodeURIComponent(s) {
        try { return decodeURIComponent(s); } catch { return s; }
    }

    function parseStateFromRoute(r) {
        const m = (r.path || '').match(/^\/project\/([^/]+)(?:\/file\/(.+))?$/);
        const projectId = m?.[1] ? safeDecodeURIComponent(m[1]) : '';
        const filePath = m?.[2]
            ? m[2].split('/').map(seg => safeDecodeURIComponent(seg)).join('/')
            : '';

        const viewFromQuery = (typeof r.query.view === 'string' && r.query.view) ? r.query.view : 'world';
        const sceneId = (typeof r.query.scene === 'string' && r.query.scene) ? r.query.scene : '';

        const view = filePath ? 'production' : viewFromQuery;
        return { projectId, filePath, sceneId, view };
    }

    function buildUrlFromState() {
        const project = projectStore.currentProject;
        const file = fileStore.selectedFile;
        const scene = sceneStore.currentScene;
        const view = viewStore.currentView || 'world';

        const query = {};
        if (view !== 'production') {
            query.view = view;
        }
        if (view === 'production' && scene?.scene) {
            query.scene = scene.scene;
        }

        if (!project) {
            return { path: '/', query };
        }

        const encodedProject = encodeURIComponent(project);
        if (view === 'production' && file) {
            const filePath = file.path || file.name;
            const encodedFilePath = filePath.split('/').map(encodeURIComponent).join('/');
            return { path: `/project/${encodedProject}/file/${encodedFilePath}`, query };
        }

        return { path: `/project/${encodedProject}`, query };
    }

    async function restoreStateFromRoute(r) {
        const { projectId, filePath, sceneId, view } = parseStateFromRoute(r);

        if (view && viewStore.currentView !== view) {
            viewStore.setView(view);
        }

        if (!projectId) return;
        if (!projectStore.projects.includes(projectId)) return;

        if (projectStore.currentProject !== projectId) {
            await projectStore.setCurrentProject(projectId);
        }

        if (view !== 'production') return;
        if (!filePath) return;

        try {
            if (fileStore.selectedFile?.path !== filePath) {
                await fileStore.setCurrentFile(projectId, filePath);
            }

            if (sceneId) {
                const scene = (sceneStore.scriptData || []).find(s => s.scene === sceneId);
                if (scene && sceneStore.currentScene !== scene) {
                    sceneStore.selectScene(scene);
                }
            }
        } catch (e) {
            console.warn('URL 恢复失败:', e);
        }
    }

    async function syncUrlToState({ replace = true } = {}) {
        if (!urlHydrated.value || isRestoringUrl.value || isSyncingUrl.value) return;

        const location = buildUrlFromState();
        const currentFullPath = router.currentRoute.value.fullPath;
        const nextFullPath = router.resolve(location).fullPath;
        if (currentFullPath === nextFullPath) return;

        isSyncingUrl.value = true;
        try {
            if (replace) {
                await router.replace(location);
            } else {
                await router.push(location);
            }
        } finally {
            isSyncingUrl.value = false;
        }
    }

    function showSaveHint() {
        saveHintVisible.value = true;
        clearTimeout(showSaveHint._t);
        showSaveHint._t = setTimeout(() => saveHintVisible.value = false, 1200);
    }

    function openSettings() { settingsVisible.value = true; }

    function onKeydown(e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            bus.emit('save-request');
        }
    }

    function sceneSelectedHandler() {
        settingsVisible.value = false;
        if (viewStore.currentView === 'blueprint') {
            viewStore.setView('production');
        }
    }

    function onLogout() {
        router.push('/login');
    }

    async function initialize() {
        try {
            const user = await getUserInfo();
            username.value = user?.username || '';
            await projectStore.loadProjects();
            isRestoringUrl.value = true;
            await restoreStateFromRoute(route);
            urlHydrated.value = true;
            isRestoringUrl.value = false;
            await syncUrlToState({ replace: true });
        } catch (e) {
            router.push('/login');
        }

        window.addEventListener('keydown', onKeydown);
        bus.on('saved', showSaveHint);
        bus.on('scene-selected', sceneSelectedHandler);
    }

    function cleanup() {
        window.removeEventListener('keydown', onKeydown);
        bus.off('saved', showSaveHint);
        bus.off('scene-selected', sceneSelectedHandler);
    }

    // Pre-hydration check (synchronous)
    const initialSync = () => {
        const { view } = parseStateFromRoute(route);
        if (view && viewStore.currentView !== view) {
            viewStore.setView(view);
        }
    };

    onMounted(() => {
        chatStore.registerContextProvider(() => {
            if (viewStore.currentView === 'world') {
                const inspiration = projectStore.currentInspiration || '';
                if (inspiration) return `【当前灵感工坊内容】\n${inspiration}`;
            }
            if (viewStore.currentView === 'production') {
                if (sceneStore.currentScene) {
                    try {
                        const lines = serializeToArc([sceneStore.currentScene]);
                        return lines.join('\n');
                    } catch (e) {
                        console.warn('序列化场景失败', e);
                    }
                }
            }
            return '';
        });

        initialize();
    });

    onBeforeUnmount(cleanup);

    watch([
        () => projectStore.currentProject,
        () => fileStore.selectedFile,
        () => sceneStore.currentScene,
        () => viewStore.currentView
    ], () => {
        syncUrlToState({ replace: true });
    });

    watch(
        () => router.currentRoute.value.fullPath,
        async () => {
            if (!urlHydrated.value || isSyncingUrl.value) return;
            isRestoringUrl.value = true;
            try {
                await restoreStateFromRoute(router.currentRoute.value);
            } finally {
                isRestoringUrl.value = false;
            }
        },
        { flush: 'post' }
    );

    watch(() => sceneStore.currentScene, () => {
        settingsVisible.value = false;
    });

    return {
        viewStore,
        projectStore,
        username,
        autoSaveEnabled,
        saveHintVisible,
        settingsVisible,
        versionManagerVisible,
        aiSidebarVisible,
        openSettings,
        onLogout,
        initialSync
    };
}
