import { ref, onMounted, onBeforeUnmount } from 'vue';

type PanelBounds = {
  sidebarMin: number;
  sidebarMax: number;
  inspectorMin: number;
  inspectorMax: number;
  aiMin: number;
  aiMax: number;
};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function getPanelBounds(viewportWidth: number): PanelBounds {
  if (viewportWidth <= 1280) {
    return {
      sidebarMin: 170,
      sidebarMax: 240,
      inspectorMin: Math.max(260, Math.round(viewportWidth * 0.21)),
      inspectorMax: 320,
      aiMin: Math.max(280, Math.round(viewportWidth * 0.23)),
      aiMax: 360,
    };
  }

  if (viewportWidth <= 1520) {
    return {
      sidebarMin: 170,
      sidebarMax: 280,
      inspectorMin: Math.round(viewportWidth * 0.2),
      inspectorMax: 420,
      aiMin: Math.round(viewportWidth * 0.22),
      aiMax: 460,
    };
  }

  return {
    sidebarMin: 170,
    sidebarMax: 340,
    inspectorMin: Math.min(600, Math.round(viewportWidth * 0.18)),
    inspectorMax: 600,
    aiMin: Math.min(800, Math.round(viewportWidth * 0.2)),
    aiMax: 800,
  };
}

export function useResizer() {
  const sidebarWidth = ref(220);
  const inspectorWidth = ref(320);
  const aiSidebarWidth = ref(380);

  const isResizing = ref(false);
  let currentResizer: HTMLElement | null = null;
  let startX = 0;
  let startWidth = 0;

  function clampPanelSizes() {
    const viewportWidth = window.innerWidth || 1440;
    const bounds = getPanelBounds(viewportWidth);

    sidebarWidth.value = clamp(sidebarWidth.value, bounds.sidebarMin, bounds.sidebarMax);
    inspectorWidth.value = clamp(inspectorWidth.value, bounds.inspectorMin, bounds.inspectorMax);
    aiSidebarWidth.value = clamp(aiSidebarWidth.value, bounds.aiMin, bounds.aiMax);

    const reservedSideWidths = sidebarWidth.value + inspectorWidth.value + aiSidebarWidth.value;
    const maxSideWidthTotal = Math.max(760, viewportWidth - 420);

    if (reservedSideWidths <= maxSideWidthTotal) return;

    let overflow = reservedSideWidths - maxSideWidthTotal;

    const shrinkFrom = (current: number, min: number) => {
      if (overflow <= 0) return current;
      const available = Math.max(0, current - min);
      const reduced = Math.min(available, overflow);
      overflow -= reduced;
      return current - reduced;
    };

    // 空间不足时优先让节点树让位，保证两个编辑面板仍有可用宽度。
    sidebarWidth.value = shrinkFrom(sidebarWidth.value, bounds.sidebarMin);
    inspectorWidth.value = shrinkFrom(inspectorWidth.value, bounds.inspectorMin);
    aiSidebarWidth.value = shrinkFrom(aiSidebarWidth.value, bounds.aiMin);
  }

  const savePanelSizes = () => {
    localStorage.setItem(
      'panelSizes_v4',
      JSON.stringify({
        sidebar: sidebarWidth.value,
        inspector: inspectorWidth.value,
        ai: aiSidebarWidth.value,
      }),
    );
  };

  const loadPanelSizes = () => {
    const saved = localStorage.getItem('panelSizes_v4');
    if (!saved) {
      clampPanelSizes();
      return;
    }

    try {
      const cfg = JSON.parse(saved) as Partial<Record<'sidebar' | 'inspector' | 'ai', unknown>>;
      if (typeof cfg.sidebar === 'number') sidebarWidth.value = cfg.sidebar;
      if (typeof cfg.inspector === 'number') inspectorWidth.value = cfg.inspector;
      if (typeof cfg.ai === 'number') aiSidebarWidth.value = cfg.ai;
    } catch {
      // ignore broken localStorage payload
    }

    clampPanelSizes();
  };

  const handleMouseDown = (e: MouseEvent) => {
    e.preventDefault();
    isResizing.value = true;
    currentResizer = e.currentTarget as HTMLElement | null;
    if (!currentResizer) return;

    startX = e.clientX;
    const type = currentResizer.getAttribute('data-resize');

    if (type === 'sidebar') {
      startWidth = sidebarWidth.value;
    } else if (type === 'center') {
      startWidth = inspectorWidth.value;
    } else if (type === 'inspector') {
      startWidth = aiSidebarWidth.value;
    }

    currentResizer.classList.add('active');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isResizing.value || !currentResizer) return;

    const bounds = getPanelBounds(window.innerWidth || 1440);
    const deltaX = e.clientX - startX;
    const type = currentResizer.getAttribute('data-resize');

    let newWidth = startWidth;
    if (type === 'sidebar') {
      newWidth = startWidth + deltaX;
      sidebarWidth.value = clamp(newWidth, bounds.sidebarMin, bounds.sidebarMax);
    } else if (type === 'center') {
      newWidth = startWidth - deltaX;
      inspectorWidth.value = clamp(newWidth, bounds.inspectorMin, bounds.inspectorMax);
    } else if (type === 'inspector') {
      newWidth = startWidth - deltaX;
      aiSidebarWidth.value = clamp(newWidth, bounds.aiMin, bounds.aiMax);
    }
  };

  const handleMouseUp = () => {
    isResizing.value = false;
    if (currentResizer) currentResizer.classList.remove('active');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', handleMouseUp);
    clampPanelSizes();
    savePanelSizes();
  };

  const handleWindowResize = () => {
    clampPanelSizes();
    savePanelSizes();
  };

  onMounted(() => {
    loadPanelSizes();
    window.addEventListener('resize', handleWindowResize);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleWindowResize);
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', handleMouseUp);
  });

  return {
    sidebarWidth,
    inspectorWidth,
    aiSidebarWidth,
    handleMouseDown,
  };
}
