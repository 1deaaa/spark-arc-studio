
import { onMounted } from 'vue';
import { useAiStore } from '../components/stores/aiStore';

export function useSettingsLogic() {
    const aiStore = useAiStore();

    onMounted(async () => {
        // Initial data load for the entire settings view
        // Equivalent to original loadData() which was aiStore.loadData(true, false)
        await aiStore.loadData(true);
    });

    return {
        aiStore
    };
}
