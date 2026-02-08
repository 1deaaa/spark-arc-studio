# Tauri 2 跨平台构建（汇总）

本文件合并了 Windows / Linux / macOS / Android / iOS 的构建说明。

通用约定：所有命令均在项目根目录进入 client 后执行。

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

需要 Android SDK/NDK 与 Java 环境。

### 1. 安装基础工具

1) 安装 Android Studio。
2) 在 Android Studio 中安装 SDK + NDK（推荐使用默认路径）。
3) 安装 JDK 17（Android Studio 自带的 JBR 也可用）。

### 2. 配置环境变量（Windows PowerShell）

```powershell
[System.Environment]::SetEnvironmentVariable("ANDROID_HOME", "$env:LocalAppData\Android\Sdk", "User")
$VERSION = Get-ChildItem -Name "$env:LocalAppData\Android\Sdk\ndk" | Select-Object -Last 1
[System.Environment]::SetEnvironmentVariable("NDK_HOME", "$env:LocalAppData\Android\Sdk\ndk\$VERSION", "User")
```

重新打开终端以生效。

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

之后在 Xcode 中进行签名与归档（Archive）即可发布到 App Store。
