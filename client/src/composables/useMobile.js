
import { ref, onMounted, onUnmounted, computed } from 'vue';

const isMobile = ref(false);
const isTablet = ref(false);
const windowWidth = ref(window.innerWidth);

export function useMobile() {

    const updateDimensions = () => {
        windowWidth.value = window.innerWidth;
        isMobile.value = window.innerWidth <= 768;
        isTablet.value = window.innerWidth > 768 && window.innerWidth <= 1024;
    };

    onMounted(() => {
        updateDimensions();
        window.addEventListener('resize', updateDimensions);
    });

    onUnmounted(() => {
        window.removeEventListener('resize', updateDimensions);
    });

    return {
        isMobile,
        isTablet,
        windowWidth,
        // Helper to check if we are in "compact" mode (mobile or portrait tablet)
        isCompact: computed(() => isMobile.value || (isTablet.value && window.innerWidth < window.innerHeight))
    };
}
