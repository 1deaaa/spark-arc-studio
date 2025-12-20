import { ref, onMounted, onBeforeUnmount } from 'vue';

export function useResizer() {
  const sidebarWidth = ref(250);
  const inspectorWidth = ref(300);
  const aiSidebarWidth = ref(350);
  
  const isResizing = ref(false);
  let currentResizer = null;
  let startX = 0;
  let startWidth = 0;
  let targetPanel = null;

  const handleMouseDown = (e) => {
    e.preventDefault();
    isResizing.value = true;
    currentResizer = e.currentTarget;
    startX = e.clientX;
    const type = currentResizer.getAttribute('data-resize');
    
    if (type === 'sidebar') {
      targetPanel = 'sidebar';
      startWidth = sidebarWidth.value;
    } else if (type === 'center') {
      targetPanel = 'inspector';
      startWidth = inspectorWidth.value;
    } else if (type === 'inspector') {
      targetPanel = 'ai';
      startWidth = aiSidebarWidth.value;
    }
    
    currentResizer.classList.add('active');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e) => {
    if (!isResizing.value) return;
    const deltaX = e.clientX - startX;
    const type = currentResizer.getAttribute('data-resize');
    
    let newWidth = startWidth;
    if (type === 'sidebar') {
      newWidth = startWidth + deltaX;
      sidebarWidth.value = Math.max(150, Math.min(400, newWidth));
    } else {
      newWidth = startWidth - deltaX;
      if (type === 'center') inspectorWidth.value = Math.max(200, Math.min(600, newWidth));
      if (type === 'inspector') aiSidebarWidth.value = Math.max(250, Math.min(800, newWidth));
    }
  };

  const handleMouseUp = () => {
    isResizing.value = false;
    if (currentResizer) currentResizer.classList.remove('active');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', handleMouseUp);
    savePanelSizes();
  };

  const savePanelSizes = () => {
    localStorage.setItem('panelSizes_v3', JSON.stringify({
      sidebar: sidebarWidth.value,
      inspector: inspectorWidth.value,
      ai: aiSidebarWidth.value,
    }));
  };

  const loadPanelSizes = () => {
    const saved = localStorage.getItem('panelSizes_v3');
    if (saved) {
      const cfg = JSON.parse(saved);
      if (cfg.sidebar) sidebarWidth.value = cfg.sidebar;
      if (cfg.inspector) inspectorWidth.value = cfg.inspector;
      if (cfg.ai) aiSidebarWidth.value = cfg.ai;
    }
  };

  onMounted(loadPanelSizes);

  return {
    sidebarWidth,
    inspectorWidth,
    aiSidebarWidth,
    handleMouseDown
  };
}
