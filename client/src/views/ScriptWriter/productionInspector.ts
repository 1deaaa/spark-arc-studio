import type { SceneSelectionType } from '@/components/stores/sceneStore';

type ProductionInspectorVisibilityInput = {
  isNovelWorkspace: boolean;
  settingsVisible: boolean;
  hasOpenScriptFile: boolean;
  hasCurrentScene: boolean;
  selectionType: SceneSelectionType;
};

export function hasDesktopNodeSelection(selectionType: SceneSelectionType): boolean {
  return selectionType === 'scene' || selectionType === 'dialogue' || selectionType === 'option';
}

export function shouldShowProductionInspector(input: ProductionInspectorVisibilityInput): boolean {
  if (input.settingsVisible) return true;
  if (input.isNovelWorkspace) return false;
  return input.hasOpenScriptFile || input.hasCurrentScene || hasDesktopNodeSelection(input.selectionType);
}
