class FileManager {
    constructor() {
        this.selectedFile = null;
        this.contextMenu = null;
        this.sortableInstances = [];
        this.fileTree = [];
        this.init();
    }

    init() {
        this.createContextMenu();
        this.bindEvents();
        this.loadJsonFiles();
    }

    bindEvents() {
        // 控制按钮事件
        document.getElementById('new-folder-btn').addEventListener('click', () => {
            this.createNewFolder();
        });

        document.getElementById('new-file-btn').addEventListener('click', () => {
            this.createNewJsonFile();
        });

        document.getElementById('refresh-files-btn').addEventListener('click', () => {
            this.loadJsonFiles();
        });

        // 隐藏右键菜单
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });

        // 阻止默认右键菜单
        document.getElementById('file-tree').addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });
    }

    async loadJsonFiles() {
        try {
            const response = await fetch('/api/json-files');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const fileData = await response.json();
            this.fileTree = fileData;
            this.renderFileTree(this.fileTree);
        } catch (error) {
            console.warn('无法从服务器加载文件，使用本地数据:', error);
            this.loadLocalJsonFiles();
        }
    }

    loadLocalJsonFiles() {
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
                        { name: '示例故事', type: 'json' }
                    ]
                },
                { name: '新建故事', type: 'json' }
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
            content.appendChild(icon);
        } else {
            // JSON文件缩进
            const spacer = document.createElement('span');
            spacer.style.width = '15px';
            content.appendChild(spacer);

            // JSON文件图标
            const icon = document.createElement('span');
            icon.className = 'file-icon json';
            icon.textContent = '📋';
            content.appendChild(icon);
        }

        // 文件名
        const name = document.createElement('span');
        name.className = 'file-name';
        name.textContent = item.name;
        content.appendChild(name);

        div.appendChild(content);

        // 事件绑定
        div.addEventListener('click', () => this.selectFile(div));
        div.addEventListener('dblclick', () => {
            if (item.type === 'json') {
                this.openJsonFile(item.name);
            } else {
                this.toggleFolder(div);
            }
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

        return div;
    }

    selectFile(fileElement) {
        document.querySelectorAll('.file-item.selected').forEach(item => {
            item.classList.remove('selected');
        });
        fileElement.classList.add('selected');
        this.selectedFile = fileElement;
    }

    toggleFolder(folderElement) {
        const children = folderElement.querySelector('.folder-children');
        const toggle = folderElement.querySelector('.folder-toggle');
        
        if (children) {
            const isCollapsed = children.classList.contains('collapsed');
            children.classList.toggle('collapsed');
            toggle.textContent = isCollapsed ? '▼' : '▶';
        }
    }

    openJsonFile(filename) {
        console.log(`打开JSON文件: ${filename}`);
        // 这里可以加载对应的JSON文件到场景列表
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
            menuItems.push({ text: '打开', action: () => this.openJsonFile(fileElement.dataset.name) });
            menuItems.push({ type: 'separator' });
        }
        
        menuItems.push(
            { text: '新建JSON文件', action: () => this.createNewJsonFile(fileElement) },
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
    }    createNewJsonFile(parentFolder = null) {
        const input = document.createElement('input');
        input.className = 'new-item-input';
        input.type = 'text';
        input.value = '新建故事';

        const container = this.getContainerForNewItem(parentFolder);
        container.appendChild(input);
        input.focus();
        input.select();

        const finishCreation = () => {
            const name = input.value.trim();
            if (name && name !== '新建故事') {
                // 创建新文件数据
                const newFile = { name, type: 'json' };
                
                // 添加到数据结构中
                if (parentFolder && parentFolder.dataset.type === 'folder') {
                    // 添加到父文件夹的children中
                    this.addItemToFolder(newFile, parentFolder.dataset.name);
                } else {
                    // 添加到根级别
                    this.fileTree.push(newFile);
                }
                
                // 保存并重新渲染
                this.saveFileTree(this.fileTree);
                this.renderFileTree(this.fileTree);
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
    }    createNewFolder(parentFolder = null) {
        const input = document.createElement('input');
        input.className = 'new-item-input';
        input.type = 'text';
        input.value = '新建文件夹';

        const container = this.getContainerForNewItem(parentFolder);
        container.appendChild(input);
        input.focus();
        input.select();

        const finishCreation = () => {
            const name = input.value.trim();
            if (name && name !== '新建文件夹') {
                // 创建新文件夹数据
                const newFolder = { name, type: 'folder', children: [] };
                
                // 添加到数据结构中
                if (parentFolder && parentFolder.dataset.type === 'folder') {
                    // 添加到父文件夹的children中
                    this.addItemToFolder(newFolder, parentFolder.dataset.name);
                } else {
                    // 添加到根级别
                    this.fileTree.push(newFolder);
                }
                
                // 保存并重新渲染
                this.saveFileTree(this.fileTree);
                this.renderFileTree(this.fileTree);
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
    }

    renameFile(fileElement) {
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

        const finishRename = () => {
            const newName = input.value.trim();
            if (newName && newName !== currentName) {
                nameSpan.textContent = newName;
                fileElement.dataset.name = newName;
                this.updateFileTree();
                this.renderFileTree(this.fileTree);
            }
            input.parentElement.replaceChild(nameSpan, input);
        };

        input.addEventListener('blur', finishRename);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                finishRename();
            } else if (e.key === 'Escape') {
                input.parentElement.replaceChild(nameSpan, input);
            }
        });
    }

    duplicateFile(fileElement) {
        const originalName = fileElement.dataset.name;
        const newName = originalName + '_副本';
        
        const newItem = { 
            name: newName, 
            type: fileElement.dataset.type,
            children: fileElement.dataset.type === 'folder' ? [] : undefined
        };
        
        this.updateFileTree();
        
        const parentContainer = fileElement.parentElement;
        if (parentContainer.id === 'file-tree') {
            this.fileTree.push(newItem);
        }
        
        this.saveFileTree(this.fileTree);
        this.renderFileTree(this.fileTree);
    }

    deleteFile(fileElement) {
        if (confirm(`确定要删除 "${fileElement.dataset.name}" 吗？`)) {
            this.updateFileTree();
            this.removeFromFileTree(fileElement.dataset.name, this.fileTree);
            this.saveFileTree(this.fileTree);
            this.renderFileTree(this.fileTree);
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
        });
    }

    createSortableForContainer(container) {
        const instance = Sortable.create(container, {
            group: 'file-tree',
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            
            onMove: (evt) => {
                // 禁止同容器内移动
                return evt.from !== evt.to;
            },
            
            onEnd: (evt) => {
                if (evt.from !== evt.to) {
                    this.updateFileTree();
                    this.renderFileTree(this.fileTree);
                }
            }
        });
        
        this.sortableInstances.push(instance);
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
}