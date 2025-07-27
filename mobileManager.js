// 移动端管理器
class MobileManager {
    constructor() {
        this.isMobile = false;
        this.filesPanelOpen = false;
        this.editorPanelOpen = false;
        this.sceneModalOpen = false;
        this.init();
    }

    init() {
        this.checkDevice();
        this.bindEvents();
        this.setupInitialState();
        this.addSwipeGestures();
        this.improveCloseButtonDetection();
        this.handleVirtualKeyboard();
        
        // 监听屏幕尺寸变化
        window.addEventListener('resize', () => {
            this.checkDevice();
            this.setupInitialState();
        });
    }

    checkDevice() {
        this.isMobile = window.innerWidth <= 768;
        document.body.classList.toggle('mobile', this.isMobile);
    }

    setupInitialState() {
        if (this.isMobile) {
            // 移动端初始化
            this.closeFilesPanel();
            this.closeEditorPanel();
            this.closeSceneModal();
            
            // 显示移动端工具栏
            const mobileToolbar = document.querySelector('.mobile-toolbar');
            if (mobileToolbar) {
                mobileToolbar.style.display = 'flex';
            }
        } else {
            // 桌面端初始化
            this.resetDesktopLayout();
            
            // 隐藏移动端工具栏
            const mobileToolbar = document.querySelector('.mobile-toolbar');
            if (mobileToolbar) {
                mobileToolbar.style.display = 'none';
            }
        }
    }

    bindEvents() {
        // 移动端菜单按钮
        const mobileMenuBtn = document.getElementById('mobile-menu-btn');
        if (mobileMenuBtn) {
            mobileMenuBtn.addEventListener('click', () => {
                this.toggleFilesPanel();
            });
        }

        // 移动端场景按钮
        const mobileSceneBtn = document.getElementById('mobile-scene-btn');
        if (mobileSceneBtn) {
            mobileSceneBtn.addEventListener('click', () => {
                this.toggleSceneModal();
            });
        }

        // 移动端保存按钮
        const mobileSaveBtn = document.getElementById('mobile-save-btn');
        if (mobileSaveBtn) {
            mobileSaveBtn.addEventListener('click', () => {
                document.getElementById('save-btn')?.click();
            });
        }

        // 移动端导出按钮
        const mobileExportBtn = document.getElementById('mobile-export-btn');
        if (mobileExportBtn) {
            mobileExportBtn.addEventListener('click', () => {
                document.getElementById('export-btn')?.click();
            });
        }

        // 场景弹窗关闭按钮
        const closeSceneModal = document.getElementById('close-scene-modal');
        if (closeSceneModal) {
            closeSceneModal.addEventListener('click', () => {
                this.closeSceneModal();
            });
        }

        // 遮罩层点击关闭
        const overlay = document.getElementById('mobile-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => {
                this.closeFilesPanel();
                this.closeEditorPanel();
                this.closeSceneModal();
            });
        }

        // 监听节点选择事件（用于打开编辑器）
        document.addEventListener('nodeSelected', (e) => {
            if (this.isMobile) {
                this.openEditorPanel();
            }
        });

        // 监听场景选择事件（用于打开编辑器）
        document.addEventListener('sceneSelected', (e) => {
            if (this.isMobile) {
                this.openEditorPanel();
                this.updateMobileSceneList(); // 更新场景列表
            }
        });

        // ESC键关闭面板
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isMobile) {
                this.closeFilesPanel();
                this.closeEditorPanel();
                this.closeSceneModal();
            }
        });

        // 阻止背景滚动
        this.preventBackgroundScroll();
    }

    // 文件面板相关方法
    toggleFilesPanel() {
        if (this.filesPanelOpen) {
            this.closeFilesPanel();
        } else {
            this.openFilesPanel();
        }
    }

    openFilesPanel() {
        if (!this.isMobile) return;
        
        const filePanel = document.querySelector('.file-panel');
        const overlay = document.getElementById('mobile-overlay');
        
        if (filePanel && overlay) {
            filePanel.classList.add('open');
            overlay.classList.add('show');
            this.filesPanelOpen = true;
            
            // 禁用背景滚动
            document.body.style.overflow = 'hidden';
        }
    }

    closeFilesPanel() {
        if (!this.isMobile) return;
        
        const filePanel = document.querySelector('.file-panel');
        const overlay = document.getElementById('mobile-overlay');
        
        if (filePanel) {
            filePanel.classList.remove('open');
            this.filesPanelOpen = false;
        }
        
        if (overlay && !this.editorPanelOpen && !this.sceneModalOpen) {
            overlay.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    // 编辑器面板相关方法
    openEditorPanel() {
        if (!this.isMobile) return;
        
        const rightPanel = document.querySelector('.right-panel');
        const overlay = document.getElementById('mobile-overlay');
        
        if (rightPanel && overlay) {
            rightPanel.classList.add('open');
            overlay.classList.add('show');
            this.editorPanelOpen = true;
            
            // 禁用背景滚动
            document.body.style.overflow = 'hidden';
            
            // 确保编辑器工具栏显示
            const toolbar = rightPanel.querySelector('.editor-toolbar');
            if (toolbar) {
                toolbar.style.display = 'flex';
            }
        }
    }

    closeEditorPanel() {
        if (!this.isMobile) return;
        
        const rightPanel = document.querySelector('.right-panel');
        const overlay = document.getElementById('mobile-overlay');
        
        if (rightPanel) {
            rightPanel.classList.remove('open');
            this.editorPanelOpen = false;
        }
        
        if (overlay && !this.filesPanelOpen && !this.sceneModalOpen) {
            overlay.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    // 场景弹窗相关方法
    toggleSceneModal() {
        if (this.sceneModalOpen) {
            this.closeSceneModal();
        } else {
            this.openSceneModal();
        }
    }

    openSceneModal() {
        if (!this.isMobile) return;
        
        const sceneModal = document.getElementById('mobile-scene-modal');
        const overlay = document.getElementById('mobile-overlay');
        
        if (sceneModal && overlay) {
            // 更新场景列表
            this.updateMobileSceneList();
            
            sceneModal.classList.add('open');
            overlay.classList.add('show');
            this.sceneModalOpen = true;
            
            // 禁用背景滚动
            document.body.style.overflow = 'hidden';
        }
    }

    closeSceneModal() {
        if (!this.isMobile) return;
        
        const sceneModal = document.getElementById('mobile-scene-modal');
        const overlay = document.getElementById('mobile-overlay');
        
        if (sceneModal) {
            sceneModal.classList.remove('open');
            this.sceneModalOpen = false;
        }
        
        if (overlay && !this.filesPanelOpen && !this.editorPanelOpen) {
            overlay.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    updateMobileSceneList() {
        const mobileSceneList = document.getElementById('mobile-scene-list');
        if (!mobileSceneList || !window.scriptData) return;
        
        mobileSceneList.innerHTML = '';
        
        window.scriptData.forEach(scene => {
            const sceneElement = document.createElement('div');
            sceneElement.className = 'scene-item';
            if (window.currentScene && window.currentScene.scene === scene.scene) {
                sceneElement.classList.add('selected');
            }
            sceneElement.textContent = scene.scene;
            sceneElement.addEventListener('click', () => {
                if (window.selectScene) {
                    window.selectScene(scene);
                }
                this.closeSceneModal();
            });
            
            mobileSceneList.appendChild(sceneElement);
        });
    }

    // 重置桌面布局
    resetDesktopLayout() {
        const filePanel = document.querySelector('.file-panel');
        const rightPanel = document.querySelector('.right-panel');
        const sceneModal = document.getElementById('mobile-scene-modal');
        const overlay = document.getElementById('mobile-overlay');
        
        if (filePanel) {
            filePanel.classList.remove('open');
        }
        
        if (rightPanel) {
            rightPanel.classList.remove('open');
        }
        
        if (sceneModal) {
            sceneModal.classList.remove('open');
        }
        
        if (overlay) {
            overlay.classList.remove('show');
        }
        
        this.filesPanelOpen = false;
        this.editorPanelOpen = false;
        this.sceneModalOpen = false;
        document.body.style.overflow = '';
    }

    // 阻止背景滚动
    preventBackgroundScroll() {
        let touchStartY = 0;
        
        document.addEventListener('touchstart', (e) => {
            touchStartY = e.touches[0].clientY;
        }, { passive: true });
        
        document.addEventListener('touchmove', (e) => {
            if (this.filesPanelOpen || this.editorPanelOpen || this.sceneModalOpen) {
                const touchCurrentY = e.touches[0].clientY;
                const deltaY = touchCurrentY - touchStartY;
                
                // 检查是否在面板内滚动
                const target = e.target.closest('.file-panel, .right-panel, .mobile-scene-modal');
                if (!target) {
                    e.preventDefault();
                }
            }
        }, { passive: false });
    }

    // 添加滑动手势支持
    addSwipeGestures() {
        let startX = 0;
        let startY = 0;
        let endX = 0;
        let endY = 0;
        let isSwipe = false;

        document.addEventListener('touchstart', (e) => {
            if (!this.isMobile) return;
            
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            isSwipe = false;
        }, { passive: true });

        document.addEventListener('touchmove', (e) => {
            if (!this.isMobile) return;
            
            endX = e.touches[0].clientX;
            endY = e.touches[0].clientY;
            
            // 判断是否为滑动手势
            const deltaX = Math.abs(endX - startX);
            const deltaY = Math.abs(endY - startY);
            
            if (deltaX > 10 || deltaY > 10) {
                isSwipe = true;
            }
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
            if (!this.isMobile || !isSwipe) return;
            
            const deltaX = endX - startX;
            const deltaY = endY - startY;
            const absDeltaX = Math.abs(deltaX);
            const absDeltaY = Math.abs(deltaY);
            
            // 如果水平滑动距离大于垂直滑动距离，且超过阈值
            if (absDeltaX > absDeltaY && absDeltaX > 50) {
                // 向右滑动（从左边缘开始）- 打开文件面板
                if (deltaX > 0 && startX < 30 && !this.filesPanelOpen && !this.editorPanelOpen && !this.sceneModalOpen) {
                    this.openFilesPanel();
                }
                // 向左滑动 - 关闭文件面板
                else if (deltaX < 0 && this.filesPanelOpen) {
                    this.closeFilesPanel();
                }
            }
            
            // 向下滑动关闭编辑器面板或场景弹窗
            if (absDeltaY > absDeltaX && deltaY > 50) {
                if (this.editorPanelOpen) {
                    this.closeEditorPanel();
                } else if (this.sceneModalOpen) {
                    this.closeSceneModal();
                }
            }
        }, { passive: true });
    }

    // 优化关闭按钮检测
    improveCloseButtonDetection() {
        // 为文件面板添加真实的关闭按钮
        const filePanel = document.querySelector('.file-panel');
        if (filePanel && !filePanel.querySelector('.mobile-close-btn')) {
            const closeBtn = document.createElement('button');
            closeBtn.className = 'mobile-close-btn';
            closeBtn.innerHTML = '×';
            closeBtn.style.cssText = `
                position: absolute;
                top: 10px;
                right: 15px;
                width: 30px;
                height: 30px;
                border: none;
                background: #f0f0f0;
                border-radius: 50%;
                font-size: 18px;
                cursor: pointer;
                z-index: 20;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #666;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            `;
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.closeFilesPanel();
            });
            filePanel.appendChild(closeBtn);
        }

        // 为右侧面板添加真实的关闭按钮
        const rightPanel = document.querySelector('.right-panel');
        if (rightPanel && !rightPanel.querySelector('.mobile-close-btn')) {
            const closeBtn = document.createElement('button');
            closeBtn.className = 'mobile-close-btn';
            closeBtn.innerHTML = '×';
            closeBtn.style.cssText = `
                position: absolute;
                top: 10px;
                right: 15px;
                width: 30px;
                height: 30px;
                border: none;
                background: #f0f0f0;
                border-radius: 50%;
                font-size: 18px;
                cursor: pointer;
                z-index: 20;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #666;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            `;
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.closeEditorPanel();
            });
            rightPanel.appendChild(closeBtn);
        }
    }

    // 处理虚拟键盘
    handleVirtualKeyboard() {
        let initialViewportHeight = window.innerHeight;
        
        window.addEventListener('resize', () => {
            if (!this.isMobile) return;
            
            const currentViewportHeight = window.innerHeight;
            const heightDifference = initialViewportHeight - currentViewportHeight;
            
            // 如果高度减少超过150px，认为是虚拟键盘弹出
            if (heightDifference > 150) {
                document.body.classList.add('keyboard-open');
                
                // 调整编辑器面板高度
                const rightPanel = document.querySelector('.right-panel');
                if (rightPanel && this.editorPanelOpen) {
                    rightPanel.style.height = `${currentViewportHeight - 100}px`;
                    rightPanel.style.maxHeight = `${currentViewportHeight - 100}px`;
                }
            } else {
                document.body.classList.remove('keyboard-open');
                
                // 恢复编辑器面板高度
                const rightPanel = document.querySelector('.right-panel');
                if (rightPanel) {
                    rightPanel.style.height = '';
                    rightPanel.style.maxHeight = '';
                }
            }
        });
    }

    // 提供给其他模块调用的方法
    onNodeSelect() {
        if (this.isMobile) {
            this.openEditorPanel();
        }
    }

    // 获取当前状态
    getState() {
        return {
            isMobile: this.isMobile,
            filesPanelOpen: this.filesPanelOpen,
            editorPanelOpen: this.editorPanelOpen,
            sceneModalOpen: this.sceneModalOpen
        };
    }
}

// 创建全局实例
window.mobileManager = new MobileManager();
