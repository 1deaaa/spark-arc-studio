# Tauri 2 跨平台构建（汇总）

本文件合并了 Windows / Linux / macOS / Android / iOS 的构建说明。

通用约定：所有命令均在项目根目录进入 client 后执行。

构建产物会自动同步到项目根目录的 `app-build/` 下，并按平台区分：

- `app-build/windows`
- `app-build/linux`
- `app-build/macos`
- `app-build/android`
- `app-build/ios`

---

## 通用准备

1) 安装 Node.js LTS。
2) 安装 Rust（官方 rustup）：
   - https://rustup.rs

---

## Windows 版本构建

### 1. 安装基础工具

1) 安装 Visual Studio Build Tools：
   - 勾选 "Desktop development with C++"。

### 2. 安装前端依赖

```powershell
cd client
npm install
```

### 3. 本地开发调试（可选）

```powershell
npm run tauri:dev
```

### 4. 构建 Windows 安装包

```powershell
npm run tauri:build
```

构建完成后，产物在 `client/src-tauri/target/release/bundle/` 目录下。

### 5. 常见问题

- 如果提示找不到 MSVC 或链接失败，请检查 VS Build Tools 是否正确安装。
- 如果 Rust 版本过旧，请执行 `rustup update`。

---

## Linux 版本构建

适用于 Ubuntu/Debian 系发行版，其它发行版请安装等价依赖。

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y \
  libwebkit2gtk-4.0-dev \
  libgtk-3-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev \
  build-essential
```

### 2. 安装前端依赖

```bash
cd client
npm install
```

### 3. 构建 Linux 桌面版

```bash
npm run tauri:build
```

构建完成后，产物在 `client/src-tauri/target/release/bundle/` 目录下。

---

## macOS 版本构建

需要 macOS 环境和 Xcode。

### 1. 安装基础工具

1) 安装 Xcode，并在终端执行：

```bash
xcode-select --install
```

### 2. 安装前端依赖

```bash
cd client
npm install
```

### 3. 构建 macOS 桌面版

```bash
npm run tauri:build
```

构建完成后，产物在 `client/src-tauri/target/release/bundle/` 目录下。

---

## Android 版本构建

需要 Android SDK/NDK 与 Java 环境（推荐 JDK 21 或 17）。

### 1. 安装基础工具 (Windows Scoop 方案)

推荐使用 Scoop 纯命令行配置，无需安装庞大的 Android Studio。

```powershell
# 1. 安装核心工具
scoop bucket add java
scoop install android-clt

# 2. 下载 SDK 和 NDK (运行后需输入一次 'y' 确认协议)
# 选用 API 34 (Android 14) 和 NDK r26，确保主流兼容性
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0" "ndk;26.3.11579264"
```

### 2. 配置环境变量（PowerShell）

必须配置 `ANDROID_HOME` 和 `NDK_HOME` 才能让 Tauri 识别。请在 PowerShell 中执行：

```powershell
# 设置 ANDROID_HOME
$android_home = "$env:USERPROFILE\scoop\apps\android-clt\current"
[Environment]::SetEnvironmentVariable("ANDROID_HOME", $android_home, "User")

# 设置 NDK_HOME (指向刚才下载的版本)
$ndk_path = Join-Path $android_home "ndk\26.3.11579264"
[Environment]::SetEnvironmentVariable("NDK_HOME", $ndk_path, "User")
```

执行完毕后，**必须重启终端**以生效。可通过 `cargo tauri info` 验证环境。

### 3. 初始化 Android 工程（只需一次）

```powershell
cd client
npm install
npm run tauri -- android init
```

### 4. 调试运行（可选）

```powershell
npm run tauri -- android dev
```

### 5. 生成发布包

生成 AAB（推荐提交 Google Play）：

```powershell
npm run tauri -- android build -- --aab
```

如需 APK，可去除 `-- --aab` 参数。

构建完成后，产物在 `client/src-tauri/gen/android/` 对应输出目录中。

---

## iOS 版本构建

必须在 macOS + Xcode 环境中构建。

### 1. 初始化 iOS 工程（只需一次）

```bash
cd client
npm install
npm run tauri -- ios init
```

### 2. 构建并在 Xcode 打开

```bash
npm run tauri -- ios build -- --open
```