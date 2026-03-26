import { defineStore } from 'pinia';
import { ref } from 'vue';

export type AppViewKey =
  | 'muse'
  | 'world'
  | 'lorebook'
  | 'synopsis'
  | 'structure'
  | 'production'
  | 'engine'
  | 'style'
  | 'blueprint'
  | 'player'
  | 'settings'
  | 'admin'
  | 'chat';

export const useViewStore = defineStore('view', () => {
  // 'muse' | 'world' | 'synopsis' | 'structure' | 'production' | 'style' | 'blueprint' | 'settings' | 'admin' | 'chat'
  const currentView = ref<AppViewKey>('world');

  function setView(view: AppViewKey) {
    currentView.value = view;
  }

  return {
    currentView,
    setView
  };
});
