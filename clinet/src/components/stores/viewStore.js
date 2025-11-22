import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useViewStore = defineStore('view', () => {
  // 'muse' | 'world' | 'structure' | 'production' | 'style' | 'bridge'
  const currentView = ref('production'); 

  function setView(view) {
    currentView.value = view;
  }

  return {
    currentView,
    setView
  };
});
