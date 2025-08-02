class FileManager {
    constructor() {
        this.selectedFile = null;
        this.currentProject = null;
        this.contextMenu = null;
        this.sortableInstances = [];
        this.fileTree = [];
        this.init();
    }    async init() {
        this.createContextMenu();
        this.bindEvents();
        await this.loadProjects();
    }

    bindEvents() {
        // 项目管理事件
        document.getElementById('project-dropdown').addEventListener('change', (e) => {
            this.switchProject(e.target.value);
        });
        document.getElementById('new-project-btn').addEventListener('click', () => {
            this.createNewProject();
        });
        document.getElementById('delete-project-btn').addEventListener('click', () => {
            this.deleteCurrentProject();
        });

        // 文件控制按钮事件
        document.getElementById('new-folder-btn').addEventListener('click', () => {
            this.createNewFolder();
        });        
        document.getElementById('new-file-btn').addEventListener('click', () => {
            this.createNewStoryFile();
        });
        
        // 世界观和角色设定按钮已移除
        
        document.getElementById('refresh-files-btn').addEventListener('click', () => {
            this.loadStoryFiles(this.currentProject);
        });

        // 隐藏右键菜单
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });

        // 阻止默认右键菜单
        document.getElementById('file-tree').addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });    }    async loadJsonFiles() {
        return await this.loadStoryFiles();
    }

    async loadProjects() {
        try {
            const response = await window.authManager.makeAuthenticatedRequest('/api/projects');
            if (!response || !response.ok) {
                throw new Error('无法加载项目列表');
            }
            const projects = await response.json();
            const dropdown = document.getElementById('project-dropdown');
            dropdown.innerHTML = '';

            if (projects.length > 0) {
                projects.forEach(project => {
                    const option = document.createElement('option');
                    option.value = project;
                    option.textContent = project;
                    dropdown.appendChild(option);
                });
                this.switchProject(projects[0]);
            } else {
                // 没有项目时提示创建
                const option = document.createElement('option');
                option.textContent = '请先创建项目';
                option.disabled = true;
                dropdown.appendChild(option);
                this.fileTree = [];
                this.renderFileTree([]);
            }
        } catch (error) {
            console.error('加载项目失败:', error);
            alert('加载项目列表失败');
        }
    }

    async switchProject(projectName) {
        this.currentProject = projectName;
        const dropdown = document.getElementById('project-dropdown');
        dropdown.value = projectName;
        await this.loadStoryFiles(projectName);
    }

    async loadStoryFiles(projectName) {
        if (!projectName) {
            this.fileTree = [];
            this.renderFileTree([]);
            return;
        }
        try {
            // 使用认证管理器的请求方法
            const response = await window.authManager.makeAuthenticatedRequest(`/api/story-files/${projectName}`);
            
            if (!response) {
                // 认证失败，authManager已经处理重定向
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const fileData = await response.json();
            
            // 显示所有文件夹和.story文件
            this.fileTree = fileData;
            this.renderFileTree(this.fileTree);
        } catch (error) {
            console.warn('无法从服务器加载文件，使用本地数据:', error);
            this.loadLocalStoryFiles();
        }
    }    loadLocalStoryFiles() {
        const savedFiles = localStorage.getItem('fileTree');
        let fileTree = [];
        
        if (savedFiles) {
            fileTree = JSON.parse(savedFiles);
        } else {
            fileTree = [
                {
                    name: '示例文件夹',
                    type: 'folder',
                    children: [
                        { name: '示例故事', type: 'story' }
                    ]
                },
                { name: '新建故事', type: 'story' }
            ];
            this.saveFileTree(fileTree);
        }
        
        this.fileTree = fileTree;
        this.renderFileTree(this.fileTree);
    }

    renderFileTree(items) {
        const container = document.getElementById('file-tree');
        if (!container) return;
        
        container.innerHTML = '';
        const sortedItems = this.sortItems(items);
        
        sortedItems.forEach(item => {
            const element = this.createFileElement(item, '');
            container.appendChild(element);
        });

        this.initializeSortable();
    }

    sortItems(items) {
        return [...items].sort((a, b) => {
            if (a.type === 'folder' && b.type !== 'folder') return -1;
            if (a.type !== 'folder' && b.type === 'folder') return 1;
            return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
        });
    }    createFileElement(item, path) {
        const div = document.createElement('div');
        div.className = 'file-item';
        div.dataset.name = item.name;
        div.dataset.type = item.type;
        div.dataset.path = path;

        const content = document.createElement('div');
        content.className = 'file-item-content';

        if (item.type === 'folder') {
            // 文件夹切换按钮
            const toggle = document.createElement('span');
            toggle.className = 'folder-toggle';
            toggle.textContent = '▼';
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleFolder(div);
            });
            content.appendChild(toggle);

            // 文件夹图标
            const icon = document.createElement('span');
            icon.className = 'file-icon folder';
            icon.textContent = '📁';
            content.appendChild(icon);        } else {
            // STORY文件缩进
            const spacer = document.createElement('span');
            spacer.style.width = '15px';
            content.appendChild(spacer);

            // STORY文件图标
            const icon = document.createElement('span');
            icon.className = 'file-icon story';
            icon.textContent = '📋';
            content.appendChild(icon);
        }

        // 文件名
        const name = document.createElement('span');
        name.className = 'file-name';
        name.textContent = item.name;
        content.appendChild(name);        div.appendChild(content);

        // 事件绑定
        div.addEventListener('click', (e) => {
            e.stopPropagation();
            
            this.selectFile(div);
            // 单击story文件时，由selectFile函数统一处理打开逻辑
        });
          div.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            
            if (item.type === 'folder') {
                this.toggleFolder(div);
            }
            // STORY文件的双击已经在单击中处理了
        });
        div.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.showContextMenu(e, div);
        });

        // 添加子项
        if (item.type === 'folder' && item.children) {
            const childrenContainer = document.createElement('div');
            childrenContainer.className = 'folder-children';
            
            const sortedChildren = this.sortItems(item.children);
            sortedChildren.forEach(child => {
                const childElement = this.createFileElement(child, path + '/' + item.name);
                childrenContainer.appendChild(childElement);
            });

            div.appendChild(childrenContainer);
        }

        return div;    }    selectFile(fileElement) {
        document.querySelectorAll('.file-item.selected').forEach(item => {
            item.classList.remove('selected');
        });
        fileElement.classList.add('selected');
        this.selectedFile = fileElement;
        
        // 如果是JSON文件或TXT文件，立即加载内容
        if (fileElement.dataset.type === 'json' || fileElement.dataset.type === 'file' && fileElement.dataset.name.endsWith('.txt')) {
            // 获取完整路径并传递给loadFileContent
            const fullPath = this.getItemPath(fileElement);
            this.loadFileContent(fullPath);
        }
        
        // 如果是story文件，确保能正确打开
        if (fileElement.dataset.type === 'story') {
            const fullPath = this.getItemPath(fileElement);
            this.openStoryFile(fullPath);
        }
    }

    toggleFolder(folderElement) {
        const children = folderElement.querySelector('.folder-children');
        const toggle = folderElement.querySelector('.folder-toggle');
        
        if (children) {
            const isCollapsed = children.classList.contains('collapsed');
            children.classList.toggle('collapsed');
            toggle.textContent = isCollapsed ? '▼' : '▶';        }    }    openStoryFile(fullPath) {
        console.log(`打开STORY文件: ${fullPath}`);
        this.loadFileContent(fullPath);
    }async loadFileContent(filename) {
        // 检查是否有未保存的修改
        const canProceed = await checkAndPromptSave();
        if (!canProceed) {
            return; // 用户取消了切换文件
        }
        
        try {
            // 确定文件类型
            const isTxtFile = filename.endsWith('.txt');
            const isStoryFile = filename.endsWith('.story');
            
            // 构建API端点
            let endpoint;
            if (isTxtFile) {
                // 对于txt文件，我们需要一个不同的端点来获取纯文本内容
                // 这里假设后端有一个/api/file-content-txt端点来处理txt文件
                endpoint = `/api/file-content-txt/${this.currentProject}/${encodeURIComponent(filename)}`;
            } else {
                // 对于story文件，使用现有的端点
                endpoint = `/api/file-content/${this.currentProject}/${encodeURIComponent(filename)}`;
            }
            
            // 使用认证管理器的请求方法
            const response = window.authManager ?
                await window.authManager.makeAuthenticatedRequest(endpoint) :
                await fetch(endpoint);
            
            if (!response) {
                // 认证失败，authManager已经处理重定向
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            if (isTxtFile) {
                // 处理txt文件
                const textContent = await response.text();
                // 这里我们需要调用一个函数来显示txt文件的编辑器
                // 例如，可以创建一个简单的文本区域来编辑txt文件
                this.showTxtEditor(filename, textContent);
            } else {
                // 处理story文件 (JSON)
                const data = await response.json();
                // 更新全局变量
                if (Array.isArray(data)) {
                    // 直接更新全局变量（不使用window前缀）
                    scriptData = data;
                    
                    // 重新初始化ID管理器
                    if (window.idManager) {
                        window.idManager.initializeFromScriptData(scriptData);
                        
                        // 检查并修复重复ID
                        const fixedCount = window.idManager.validateAndFixAllScenes(scriptData);
                        if (fixedCount > 0) {
                            console.log(`文件加载时修复了 ${fixedCount} 个重复ID问题`);
                        }
                    }
                    
                    // 设置当前文件名（用于保存功能）
                    if (typeof setCurrentFileName === 'function') {
                        setCurrentFileName(filename);
                    }
                    
                    // 标记为已保存状态
                    if (typeof markAsSaved === 'function') {
                        markAsSaved();
                    }
                    
                    // 选择第一个场景
                    currentScene = data.length > 0 ? data[0] : null;
                    currentNode = null;
                    nodeParent = null;
                    
                    // 调用渲染函数
                    if (typeof renderSceneList === 'function') {
                        renderSceneList();
                    }
                    if (typeof renderDialogueTree === 'function') {
                        renderDialogueTree();
                    }
                    if (typeof showSceneEditor === 'function' && currentScene) {
                        showSceneEditor();
                    } else if (typeof hideAllEditors === 'function') {
                        hideAllEditors();
                    }
                    
                    console.log(`已加载文件: ${filename}，包含 ${data.length} 个场景`);
                } else {
                    console.warn('文件格式不正确:', data);
                    alert('文件格式不正确，请确保是有效的JSON数组格式');
                }
            }
        } catch (error) {
            console.error('加载文件失败:', error);
            alert(`加载文件失败: ${error.message}`);
        }
    }

    createContextMenu() {
        this.contextMenu = document.createElement('div');
        this.contextMenu.className = 'context-menu';
        this.contextMenu.style.display = 'none';
        document.body.appendChild(this.contextMenu);
    }

    showContextMenu(event, fileElement) {
        this.contextMenu.innerHTML = '';
        
        const isFolder = fileElement.dataset.type === 'folder';
          const menuItems = [];
          if (!isFolder) {
            menuItems.push({ text: '打开', action: () => {
                const fullPath = this.getItemPath(fileElement);
                this.openStoryFile(fullPath);
            }});
            menuItems.push({ type: 'separator' });
        }
        
        menuItems.push(
            { text: '新建STORY文件', action: () => this.createNewStoryFile(fileElement) },
            { text: '新建文件夹', action: () => this.createNewFolder(fileElement) },
            { type: 'separator' },
            { text: '重命名', action: () => this.renameFile(fileElement) },
            { text: '复制', action: () => this.duplicateFile(fileElement) },
            { text: '删除', action: () => this.deleteFile(fileElement) }
        );

        menuItems.forEach(item => {
            if (item.type === 'separator') {
                const separator = document.createElement('div');
                separator.className = 'context-menu-separator';
                this.contextMenu.appendChild(separator);
            } else {
                const menuItem = document.createElement('div');
                menuItem.className = 'context-menu-item';
                menuItem.textContent = item.text;
                menuItem.addEventListener('click', (e) => {
                    e.stopPropagation();
                    item.action();
                    this.hideContextMenu();
                });
                this.contextMenu.appendChild(menuItem);
            }
        });

        this.contextMenu.style.display = 'block';
        this.contextMenu.style.left = event.pageX + 'px';
        this.contextMenu.style.top = event.pageY + 'px';

        // 防止菜单超出视窗
        const rect = this.contextMenu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            this.contextMenu.style.left = (event.pageX - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            this.contextMenu.style.top = (event.pageY - rect.height) + 'px';
        }
    }

    hideContextMenu() {
        if (this.contextMenu) {
            this.contextMenu.style.display = 'none';
        }
    }    async createNewStoryFile(parentFolder = null) {
        const input = document.createElement('input');
        input.className = 'new-item-input';
        input.type = 'text';
        input.value = '新建故事';

        const container = this.getContainerForNewItem(parentFolder);
        container.appendChild(input);
        input.focus();
        input.select();

        const finishCreation = async () => {
            const name = input.value.trim();
            if (name && name !== '新建故事') {
                try {                    // 构建文件路径
                    let filePath = name; // 不再添加 .story 后缀
                    if (parentFolder && parentFolder.dataset.type === 'folder') {
                        const parentPath = this.getItemPath(parentFolder);
                        filePath = parentPath ? `${parentPath}/${filePath}` : filePath;
                    }
                      // 调用后端API创建文件
                    const response = window.authManager ? 
                        await window.authManager.makeAuthenticatedRequest('/api/file-operations/create', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                type: 'file',
                                path: filePath,
                                projectName: this.currentProject
                            })
                        }) :
                        await fetch('/api/file-operations/create', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                type: 'file',
                                path: filePath,
                                projectName: this.currentProject
                            })
                        });
                    
                    if (!response) {
                        // 认证失败，authManager已经处理重定向
                        return;
                    }
                    
                    const result = await response.json();
                    if (result.success) {
                        // 重新加载文件树
                        await this.loadStoryFiles(this.currentProject);
                    } else {
                        alert(result.message);
                    }
                } catch (error) {
                    console.error('创建文件失败:', error);
                    alert('创建文件失败');
                }
            }
            if (input.parentNode) {
                container.removeChild(input);
            }
        };

        input.addEventListener('blur', finishCreation);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                finishCreation();
            } else if (e.key === 'Escape') {
                if (input.parentNode) {
                    container.removeChild(input);
                }
            }
        });
    }    async createNewFolder(parentFolder = null) {
        const input = document.createElement('input');
        input.className = 'new-item-input';
        input.type = 'text';
        input.value = '新建文件夹';

        const container = this.getContainerForNewItem(parentFolder);
        container.appendChild(input);
        input.focus();
        input.select();

        const finishCreation = async () => {
            const name = input.value.trim();
            if (name && name !== '新建文件夹') {
                try {
                    // 构建文件夹路径
                    let folderPath = name;
                    if (parentFolder && parentFolder.dataset.type === 'folder') {
                        const parentPath = this.getItemPath(parentFolder);
                        folderPath = parentPath ? `${parentPath}/${folderPath}` : folderPath;
                    }
                      // 调用后端API创建文件夹
                    const response = window.authManager ? 
                        await window.authManager.makeAuthenticatedRequest('/api/file-operations/create', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                type: 'folder',
                                path: folderPath,
                                projectName: this.currentProject
                            })
                        }) :
                        await fetch('/api/file-operations/create', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                type: 'folder',
                                path: folderPath,
                                projectName: this.currentProject
                            })
                        });
                    
                    if (!response) {
                        // 认证失败，authManager已经处理重定向
                        return;
                    }
                    
                    const result = await response.json();
                    if (result.success) {
                        // 重新加载文件树
                        await this.loadStoryFiles(this.currentProject);
                    } else {
                        alert(result.message);
                    }
                } catch (error) {
                    console.error('创建文件夹失败:', error);
                    alert('创建文件夹失败');
                }
            }
            if (input.parentNode) {
                container.removeChild(input);
            }
        };

        input.addEventListener('blur', finishCreation);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                finishCreation();
            } else if (e.key === 'Escape') {
                if (input.parentNode) {
                    container.removeChild(input);
                }
            }
        });
    }

    getContainerForNewItem(parentFolder) {
        if (parentFolder && parentFolder.dataset.type === 'folder') {
            let childrenContainer = parentFolder.querySelector('.folder-children');
            if (!childrenContainer) {
                childrenContainer = document.createElement('div');
                childrenContainer.className = 'folder-children';
                parentFolder.appendChild(childrenContainer);
            }
            childrenContainer.classList.remove('collapsed');
            const toggle = parentFolder.querySelector('.folder-toggle');
            if (toggle) toggle.textContent = '▼';
            
            return childrenContainer;
        }
        return document.getElementById('file-tree');
    }    async renameFile(fileElement) {
        const nameSpan = fileElement.querySelector('.file-name');
        const currentName = nameSpan.textContent;

        const input = document.createElement('input');
        input.className = 'new-item-input';
        input.type = 'text';
        input.value = currentName;
        input.style.width = nameSpan.offsetWidth + 'px';

        nameSpan.parentElement.replaceChild(input, nameSpan);
        input.focus();
        input.select();

        const finishRename = async () => {
            const newName = input.value.trim();
            if (newName && newName !== currentName) {
                try {
                    const oldPath = this.getItemPath(fileElement);
                    const newPath = oldPath.replace(new RegExp(currentName + '$'), newName);
                    
                    // 如果是JSON文件，添加.json后缀
                    let oldFilePath = oldPath;
                    let newFilePath = newPath;
                    if (fileElement.dataset.type === 'json') {
                        oldFilePath += '.json';
                        newFilePath += '.json';
                    }
                      const response = window.authManager ? 
                        await window.authManager.makeAuthenticatedRequest('/api/file-operations/rename', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                oldPath: oldFilePath,
                                newPath: newFilePath,
                                projectName: this.currentProject
                            })
                        }) :
                        await fetch('/api/file-operations/rename', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                oldPath: oldFilePath,
                                newPath: newFilePath,
                                projectName: this.currentProject
                            })
                        });
                    
                    if (!response) {
                        // 认证失败，authManager已经处理重定向
                        return;
                    }
                    
                    const result = await response.json();
                    if (result.success) {
                        // 重新加载文件树
                        await this.loadJsonFiles();
                    } else {
                        alert(result.message);
                        input.parentElement.replaceChild(nameSpan, input);
                    }
                } catch (error) {
                    console.error('重命名失败:', error);
                    alert('重命名失败');
                    input.parentElement.replaceChild(nameSpan, input);
                }
            } else {
                input.parentElement.replaceChild(nameSpan, input);
            }
        };

        input.addEventListener('blur', finishRename);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                finishRename();
            } else if (e.key === 'Escape') {
                input.parentElement.replaceChild(nameSpan, input);
            }
        });    }    async duplicateFile(fileElement) {
        const originalName = fileElement.dataset.name;
        const itemPath = this.getItemPath(fileElement);
        
        // 生成新文件名
        let newName = `${originalName} - 副本`;
        let counter = 1;
        
        // 确保新文件名不重复
        while (this.fileExists(newName, fileElement.parentElement)) {
            newName = `${originalName} - 副本 (${counter})`;
            counter++;
        }
        
        try {
            let sourceFilePath = itemPath;
            let targetFilePath = itemPath.replace(new RegExp(originalName + '$'), newName);
            
            // 如果是JSON文件，添加.json后缀
            if (fileElement.dataset.type === 'json') {
                sourceFilePath += '.json';
                targetFilePath += '.json';
            }
              const response = window.authManager ? 
                await window.authManager.makeAuthenticatedRequest('/api/file-operations/copy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        sourcePath: sourceFilePath,
                        targetPath: targetFilePath,
                        projectName: this.currentProject
                    })
                }) :
                await fetch('/api/file-operations/copy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        sourcePath: sourceFilePath,
                        targetPath: targetFilePath,
                        projectName: this.currentProject
                    })
                });
            
            if (!response) {
                // 认证失败，authManager已经处理重定向
                return;
            }
            
            const result = await response.json();
            if (result.success) {
                // 重新加载文件树
                await this.loadJsonFiles();
                console.log(`已复制文件: ${originalName} -> ${newName}`);
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error('复制失败:', error);
            alert('复制失败');
        }
    }
    
    fileExists(name, container) {
        const items = container.querySelectorAll('.file-item');
        for (let item of items) {
            if (item.dataset.name === name) {
                return true;
            }
        }
        return false;
    }async deleteFile(fileElement) {
        if (confirm(`确定要删除 "${fileElement.dataset.name}" 吗？`)) {
            try {
                const itemPath = this.getItemPath(fileElement);
                let filePath = itemPath;
                
                // 如果是JSON文件，添加.json后缀
                if (fileElement.dataset.type === 'json') {
                    filePath += '.json';
                }
                  const response = window.authManager ? 
                    await window.authManager.makeAuthenticatedRequest('/api/file-operations/delete', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            path: filePath,
                            projectName: this.currentProject
                        })
                    }) :
                    await fetch('/api/file-operations/delete', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            path: filePath,
                            projectName: this.currentProject
                        })
                    });
                
                if (!response) {
                    // 认证失败，authManager已经处理重定向
                    return;
                }
                
                const result = await response.json();
                if (result.success) {
                    // 重新加载文件树
                    await this.loadJsonFiles();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error('删除失败:', error);
                alert('删除失败');
            }
        }
    }

    removeFromFileTree(name, items) {
        for (let i = 0; i < items.length; i++) {
            if (items[i].name === name) {
                items.splice(i, 1);
                return true;
            }
            if (items[i].children && this.removeFromFileTree(name, items[i].children)) {
                return true;
            }
        }
        return false;
    }

    initializeSortable() {
        // 销毁现有实例
        this.sortableInstances.forEach(instance => {
            if (instance && instance.destroy) {
                instance.destroy();
            }
        });
        this.sortableInstances = [];

        // 为容器创建拖拽实例
        this.createSortableForContainer(document.getElementById('file-tree'));
        
        document.querySelectorAll('.folder-children').forEach(container => {
            this.createSortableForContainer(container);
        });    }    createSortableForContainer(container) {
        const instance = Sortable.create(container, {
            group: 'file-tree',
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            
            // 只有选中的文件才能拖拽
            filter: (evt, target) => {
                const fileItem = target.closest('.file-item');
                return !fileItem || !fileItem.classList.contains('selected');
            },
            
            onStart: (evt) => {
                // 记录拖拽开始时的源路径
                const draggedElement = evt.item;
                draggedElement._originalPath = this.getItemPath(draggedElement);
                console.log('记录原始路径:', draggedElement._originalPath);
            },
            
            onMove: (evt) => {
                // 禁止同容器内移动
                return evt.from !== evt.to;
            },
            
            onEnd: async (evt) => {
                if (evt.from !== evt.to) {
                    await this.handleFileDrop(evt);
                }
            }
        });
        
        this.sortableInstances.push(instance);
    }    async handleFileDrop(evt) {
        try {
            const draggedElement = evt.item;
            const sourceContainer = evt.from;
            const targetContainer = evt.to;
            
            // 使用保存的原始路径
            const sourcePath = draggedElement._originalPath || this.getItemPath(draggedElement);
            console.log('源路径:', sourcePath);
            
            // 计算目标路径
            let targetPath;
            
            // 找到目标容器对应的文件夹
            const targetFolder = targetContainer.closest('.file-item');
            console.log('目标文件夹:', targetFolder);
            
            if (targetFolder && targetFolder.dataset.type === 'folder') {
                // 拖拽到文件夹内
                const targetFolderPath = this.getItemPath(targetFolder);
                targetPath = targetFolderPath ? `${targetFolderPath}/${draggedElement.dataset.name}` : draggedElement.dataset.name;
                console.log('目标文件夹路径:', targetFolderPath);
            } else {
                // 拖拽到根目录
                targetPath = draggedElement.dataset.name;
            }
            
            console.log('计算的目标路径:', targetPath);
            
            // 如果源路径和目标路径相同，则不需要移动
            if (sourcePath === targetPath) {
                console.log('源路径和目标路径相同，取消移动');
                return;
            }
            
            // 如果是JSON文件，添加.json后缀
            let sourceFilePath = sourcePath;
            let targetFilePath = targetPath;
            if (draggedElement.dataset.type === 'json') {
                sourceFilePath += '.json';
                targetFilePath += '.json';
            }
            
            console.log('最终源文件路径:', sourceFilePath);
            console.log('最终目标文件路径:', targetFilePath);
            
            // 清理临时属性
            delete draggedElement._originalPath;
              // 调用后端API移动文件
            const response = window.authManager ? 
                await window.authManager.makeAuthenticatedRequest('/api/file-operations/move', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        sourcePath: sourceFilePath,
                        targetPath: targetFilePath,
                        projectName: this.currentProject
                    })
                }) :
                await fetch('/api/file-operations/move', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        sourcePath: sourceFilePath,
                        targetPath: targetFilePath,
                        projectName: this.currentProject
                    })
                });
            
            if (!response) {
                // 认证失败，authManager已经处理重定向
                return;
            }
            
            const result = await response.json();
            if (result.success) {
                // 重新加载文件树
                await this.loadJsonFiles();
            } else {
                alert(result.message);
                // 恢复原始位置
                sourceContainer.appendChild(draggedElement);
            }
        } catch (error) {
            console.error('移动文件失败:', error);
            alert('移动文件失败');
            // 重新加载文件树以恢复状态
            await this.loadJsonFiles();
        }
    }

    updateFileTree() {
        const fileTree = this.extractFileTree(document.getElementById('file-tree'));
        this.fileTree = fileTree;
        this.saveFileTree(fileTree);
    }

    extractFileTree(container) {
        const items = [];
        container.querySelectorAll(':scope > .file-item').forEach(item => {
            const itemData = {
                name: item.dataset.name,
                type: item.dataset.type
            };

            if (item.dataset.type === 'folder') {
                const children = item.querySelector('.folder-children');
                if (children) {
                    itemData.children = this.extractFileTree(children);
                } else {
                    itemData.children = [];
                }
            }

            items.push(itemData);
        });
        return items;
    }

    saveFileTree(fileTree) {
        localStorage.setItem('fileTree', JSON.stringify(fileTree));
    }

    getFileTree() {
        return this.fileTree;
    }

    getSelectedFile() {
        return this.selectedFile ? this.selectedFile.dataset.name : null;
    }

    addItemToFolder(newItem, folderName) {
        const addToItems = (items) => {
            for (let item of items) {
                if (item.type === 'folder' && item.name === folderName) {
                    if (!item.children) {
                        item.children = [];
                    }
                    item.children.push(newItem);
                    return true;
                }
                if (item.children && addToItems(item.children)) {
                    return true;
                }
            }
            return false;
        };
        
        return addToItems(this.fileTree);
    }

    getItemPath(fileElement) {
        const buildPath = (element) => {
            const parts = [];
            let current = element;
            
            while (current && current.classList.contains('file-item')) {
                parts.unshift(current.dataset.name);
                
                // 向上查找父文件夹
                current = current.parentElement;
                while (current && !current.classList.contains('file-item')) {
                    current = current.parentElement;
                }
            }
            
            return parts.join('/');
        };
        
        return buildPath(fileElement);
    }
    async createNewProject() {
        const projectName = prompt("请输入新项目的名称:");
        if (projectName) {
            try {
                const response = await window.authManager.makeAuthenticatedRequest('/api/projects', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ projectName })
                });
                const result = await response.json();
                if (result.success) {
                    await this.loadProjects();
                    this.switchProject(projectName);
                } else {
                    alert(`创建项目失败: ${result.message}`);
                }
            } catch (error) {
                alert('创建项目时出错');
            }
        }
    }

    async deleteCurrentProject() {
        if (!this.currentProject) {
            alert("没有选中的项目");
            return;
        }
        if (confirm(`确定要删除项目 "${this.currentProject}" 吗？此操作不可撤销！`)) {
            try {
                const response = await window.authManager.makeAuthenticatedRequest(`/api/projects/${this.currentProject}`, {
                    method: 'DELETE'
                });
                const result = await response.json();
                if (result.success) {
                    await this.loadProjects();
                } else {
                    alert(`删除项目失败: ${result.message}`);
                }
            } catch (error) {
                alert('删除项目时出错');
            }
        }
    }

    /**
     * 显示TXT文件编辑器
     * @param {string} filename - 文件名
     * @param {string} content - 文件内容
     */
    showTxtEditor(filename, content) {
        // 隐藏所有现有的编辑器
        if (typeof hideAllEditors === 'function') {
            hideAllEditors();
        }
        
        // 获取节点编辑器容器
        const nodeEditor = document.getElementById('node-editor');
        if (!nodeEditor) return;
        
        // 清空编辑器内容
        nodeEditor.innerHTML = '';
        
        // 创建编辑器标题
        const title = document.createElement('h3');
        title.textContent = `编辑文件: ${filename}`;
        nodeEditor.appendChild(title);
        
        // 创建文本区域
        const textarea = document.createElement('textarea');
        textarea.id = 'txt-editor-content';
        textarea.value = content;
        textarea.style.width = '100%';
        textarea.style.height = '400px';
        textarea.style.fontFamily = 'monospace';
        textarea.style.fontSize = '14px';
        nodeEditor.appendChild(textarea);
        
        // 创建保存按钮
        const saveButton = document.createElement('button');
        saveButton.id = 'save-txt-btn';
        saveButton.textContent = '保存';
        saveButton.style.marginTop = '10px';
        saveButton.addEventListener('click', async () => {
            const updatedContent = textarea.value;
            await this.saveTxtFile(filename, updatedContent);
        });
        nodeEditor.appendChild(saveButton);
        
        // 设置当前文件名
        if (typeof setCurrentFileName === 'function') {
            setCurrentFileName(filename);
        }
    }
    
    /**
     * 保存TXT文件
     * @param {string} filename - 文件名
     * @param {string} content - 文件内容
     */
    async saveTxtFile(filename, content) {
        try {
            // 调用后端API保存文件
            // 这里假设后端有一个/api/save-txt端点来处理txt文件的保存
            const response = window.authManager ?
                await window.authManager.makeAuthenticatedRequest('/api/save-txt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        projectName: this.currentProject,
                        filename: filename,
                        content: content
                    })
                }) :
                await fetch('/api/save-txt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        projectName: this.currentProject,
                        filename: filename,
                        content: content
                    })
                });
            
            if (!response) {
                // 认证失败，authManager已经处理重定向
                return;
            }
            
            const result = await response.json();
            if (result.success) {
                alert('文件保存成功');
                // 标记为已保存状态
                if (typeof markAsSaved === 'function') {
                    markAsSaved();
                }
            } else {
                alert(`保存失败: ${result.message}`);
            }
        } catch (error) {
            console.error('保存文件失败:', error);
            alert(`保存文件失败: ${error.message}`);
        }
    }

    async createSpecialFile(filename, parentFolder = null) {
        try {
            // 对于"角色设定"，我们需要创建一个目录而不是文件
            const isCharacterSettings = filename === '角色设定';
            const fileType = isCharacterSettings ? 'folder' : 'file';
            let filePath = isCharacterSettings ? '角色设定' : filename;
            
            const response = await window.authManager.makeAuthenticatedRequest('/api/file-operations/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: fileType,
                    path: filePath,
                    projectName: this.currentProject
                })
            });
            
            const result = await response.json();
            if (result.success) {
                await this.loadStoryFiles(this.currentProject);
            } else {
                // 如果后端返回文件已存在的错误, 给用户一个更友好的提示
                if (result.message && result.message.includes('已存在')) {
                     alert(`"${filename}" 已存在于项目根目录中。`);
                } else {
                     alert(`创建文件失败: ${result.message}`);
                }
               
            }
        } catch (error) {
            alert('创建文件时出错');
        }
    }
}