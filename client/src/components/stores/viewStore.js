import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useViewStore = defineStore('view', () => {
  // 'muse' | 'world' | 'synopsis' | 'structure' | 'production' | 'style' | 'blueprint' | 'settings' | 'admin'
  const currentView = ref('world');

  function setView(view) {
    currentView.value = view;
  }

  return {
    currentView,
    setView
  };
});
