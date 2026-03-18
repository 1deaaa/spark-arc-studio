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

> 以下内容基于本项目 Tauri 2 的实际构建过程补充，优先按此流程执行。

### 1. 安装基础工具

1) 安装 Android Studio。
2) 在 Android Studio 中安装 SDK + NDK（推荐使用默认路径）。
3) 安装 JDK 17 或 JDK 21（Android Studio 自带 JBR 也可用）。
4) Windows 建议开启“开发者模式”（允许创建符号链接）。

### 2. 必要组件检查（建议先跑）

```powershell
node -v
npm -v
rustc -V
cargo -V
npx tauri -V
java -version
adb version
sdkmanager --version
rustup target list --installed
```

建议至少具备：
- Rust Android targets：`aarch64-linux-android`、`x86_64-linux-android`
- SDK 组件：`platform-tools`、`platforms;android-36`（或可用 API）、`build-tools;35.0.0`（或可用版本）、`ndk;26.x`

### 3. 配置环境变量（Windows PowerShell）

```powershell
[System.Environment]::SetEnvironmentVariable("ANDROID_HOME", "$env:LocalAppData\Android\Sdk", "User")
$VERSION = Get-ChildItem -Name "$env:LocalAppData\Android\Sdk\ndk" | Select-Object -Last 1
[System.Environment]::SetEnvironmentVariable("NDK_HOME", "$env:LocalAppData\Android\Sdk\ndk\$VERSION", "User")
```

重新打开终端以生效。

### 4. 初始化 Android 工程（只需一次）

```powershell
cd client
npm install
npm run tauri -- android init
```

> `android init` 会自动安装缺失的 Rust Android target。

### 5. 项目内必备配置（本项目）

请确认以下条件满足，否则会在构建时失败：

1) `client/src-tauri/tauri.conf.json` 的 `version` 不能是 `0.0.0`（Android 不接受）。
2) `client/src-tauri/src/lib.rs` 存在，并使用 `#[cfg_attr(mobile, tauri::mobile_entry_point)]`。
3) `client/src-tauri/Cargo.toml` 含 `[lib] crate-type = ["staticlib", "cdylib", "rlib"]`。
4) `client/src-tauri/icons/icon.png` 存在（仅有 `.ico` 会报错）。

### 6. 调试运行（可选）

```powershell
npm run tauri -- android dev
```

### 7. 生成构建包

#### 7.1 发布构建（Release）

```powershell
npm run tauri:android
```

或直接：

```powershell
npx tauri android build --apk --target aarch64
```

#### 7.2 模拟器构建（Android Emulator 推荐）

大多数模拟器是 `x86_64`，建议用：

```powershell
npx tauri android build --apk --debug --target x86_64
```

否则可能出现 ABI 不匹配导致安装失败（如 `INSTALL_FAILED_NO_MATCHING_ABIS`）。

### 8. 产物路径

- Release APK：`client/src-tauri/gen/android/app/build/outputs/apk/universal/release/`
- Debug APK：`client/src-tauri/gen/android/app/build/outputs/apk/universal/debug/`

如果使用项目脚本：

```powershell
npm run tauri:android
```

构建完成后会自动复制 Android 产物到统一目录：

- `app-build/android/apk/...`
- `app-build/android/aab/...`（如果本次构建了 AAB）

### 9. 常见问题（本项目已验证）

1) **Windows symlink 权限报错**

报错特征：创建 `libsparkarc.so` 符号链接失败。  
处理：开启 Windows 开发者模式，或使用管理员权限运行终端。

2) **APK 能构建但模拟器装不上**

常见原因：架构不匹配（打了 `aarch64` 装在 `x86_64` 模拟器）。  
处理：构建 `--target x86_64` 的 debug APK。

3) **Kotlin daemon 警告/回退**

日志可能出现 Kotlin daemon 失败后 fallback 编译，本项目可继续产出 APK，通常不阻塞。

4) **JDK 21 的 source/target 8 警告**

属于构建链兼容警告，当前不阻塞产物输出。

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
