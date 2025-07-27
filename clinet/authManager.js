// 用户认证管理
class AuthManager {
    constructor() {
        this.currentUser = null;
        this.init();
    }

    async init() {
        // 获取用户信息
        await this.loadUserInfo();
        
        // 绑定登出按钮事件
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }
    }

    async loadUserInfo() {
        try {
            const response = await fetch('/api/user/info');
            const result = await response.json();
            
            if (result.success) {
                this.currentUser = result.user;
                this.updateUserDisplay();
            } else {
                // 如果获取用户信息失败，可能是未登录
                this.handleAuthError();
            }
        } catch (error) {
            console.error('获取用户信息失败:', error);
            this.handleAuthError();
        }
    }

    updateUserDisplay() {
        const usernameDisplay = document.getElementById('username-display');
        if (usernameDisplay && this.currentUser) {
            usernameDisplay.textContent = `欢迎，${this.currentUser.username}`;
        }
    }

    async logout() {
        try {
            const response = await fetch('/api/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 清空当前用户信息
                this.currentUser = null;
                // 重定向到登录页面
                window.location.href = '/login.html';
            } else {
                console.error('登出失败:', result.message);
            }
        } catch (error) {
            console.error('登出失败:', error);
            // 即使登出请求失败，也重定向到登录页面
            window.location.href = '/login.html';
        }
    }

    handleAuthError() {
        // 认证失败，重定向到登录页面
        window.location.href = '/login.html';
    }

    // 为所有API请求添加错误处理
    async makeAuthenticatedRequest(url, options = {}) {
        try {
            const response = await fetch(url, options);
            
            // 检查是否需要重新登录
            if (response.status === 401) {
                const result = await response.json();
                if (result.require_login) {
                    this.handleAuthError();
                    return null;
                }
            }
            
            return response;
        } catch (error) {
            console.error('请求失败:', error);
            throw error;
        }
    }
}

// 初始化认证管理器
const authManager = new AuthManager();

// 导出认证管理器供其他模块使用
window.authManager = authManager;
