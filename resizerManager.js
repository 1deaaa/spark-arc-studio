class ResizerManager {
    constructor() {
        this.isResizing = false;
        this.currentResizer = null;
        this.startX = 0;
        this.startWidth = 0;
        this.targetPanel = null;
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        const resizers = document.querySelectorAll('.resizer');
        resizers.forEach(resizer => {
            resizer.addEventListener('mousedown', this.handleMouseDown.bind(this));
        });

        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));
        
        // 防止文本选择
        document.addEventListener('selectstart', (e) => {
            if (this.isResizing) {
                e.preventDefault();
            }
        });
    }

    handleMouseDown(e) {
        e.preventDefault();
        this.isResizing = true;
        this.currentResizer = e.target;
        this.startX = e.clientX;        // 根据 data-resize 属性确定要调整的面板
        const resizeType = this.currentResizer.getAttribute('data-resize');
        if (resizeType === 'file') {
            this.targetPanel = document.querySelector('.file-panel');
        } else if (resizeType === 'left') {
            this.targetPanel = document.querySelector('.left-panel');
        } else if (resizeType === 'middle') {
            this.targetPanel = document.querySelector('.right-panel');
        }

        if (this.targetPanel) {
            this.startWidth = this.targetPanel.offsetWidth;
        }

        this.currentResizer.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }

    handleMouseMove(e) {
        if (!this.isResizing || !this.targetPanel) return;

        e.preventDefault();
        const deltaX = e.clientX - this.startX;
        const resizeType = this.currentResizer.getAttribute('data-resize');
          let newWidth;
        if (resizeType === 'file') {
            // 调整文件面板宽度
            newWidth = this.startWidth + deltaX;
        } else if (resizeType === 'left') {
            // 调整左面板宽度
            newWidth = this.startWidth + deltaX;
        } else if (resizeType === 'middle') {
            // 调整右面板宽度（反向）
            newWidth = this.startWidth - deltaX;
        }

        // 应用最小和最大宽度限制
        const minWidth = parseInt(getComputedStyle(this.targetPanel).minWidth);
        const maxWidth = parseInt(getComputedStyle(this.targetPanel).maxWidth);
        
        newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
        
        this.targetPanel.style.width = newWidth + 'px';
    }

    handleMouseUp() {
        if (!this.isResizing) return;

        this.isResizing = false;
        if (this.currentResizer) {
            this.currentResizer.classList.remove('active');
        }
        this.currentResizer = null;
        this.targetPanel = null;
        
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }    // 重置面板到默认大小
    resetPanels() {
        const filePanel = document.querySelector('.file-panel');
        const leftPanel = document.querySelector('.left-panel');
        const rightPanel = document.querySelector('.right-panel');
        
        filePanel.style.width = '220px';
        leftPanel.style.width = '250px';
        rightPanel.style.width = '350px';
    }

    // 保存面板大小配置到 localStorage
    savePanelSizes() {
        const filePanel = document.querySelector('.file-panel');
        const leftPanel = document.querySelector('.left-panel');
        const rightPanel = document.querySelector('.right-panel');
        
        const config = {
            fileWidth: filePanel.offsetWidth,
            leftWidth: leftPanel.offsetWidth,
            rightWidth: rightPanel.offsetWidth
        };
        
        localStorage.setItem('panelSizes', JSON.stringify(config));
    }

    // 从 localStorage 恢复面板大小配置
    loadPanelSizes() {
        try {
            const config = JSON.parse(localStorage.getItem('panelSizes'));
            if (config) {
                const filePanel = document.querySelector('.file-panel');
                const leftPanel = document.querySelector('.left-panel');
                const rightPanel = document.querySelector('.right-panel');
                
                if (config.fileWidth) {
                    filePanel.style.width = config.fileWidth + 'px';
                }
                if (config.leftWidth) {
                    leftPanel.style.width = config.leftWidth + 'px';
                }
                if (config.rightWidth) {
                    rightPanel.style.width = config.rightWidth + 'px';
                }
            }
        } catch (error) {
            console.warn('Failed to load panel sizes from localStorage:', error);
        }
    }
}

// 在页面加载时自动初始化
document.addEventListener('DOMContentLoaded', () => {
    window.resizerManager = new ResizerManager();
    // 加载保存的面板大小
    window.resizerManager.loadPanelSizes();
});

// 在页面卸载时保存面板大小
// 页面卸载前保存面板大小
window.addEventListener('beforeunload', () => {
    if (window.resizerManager) {
        window.resizerManager.savePanelSizes();
    }
});
