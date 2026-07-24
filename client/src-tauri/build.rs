fn main() {
    println!("cargo:rerun-if-changed=../../sparkarc.json");
    println!("cargo:rerun-if-changed=../../scripts/sparkarc-config.mjs");
    println!("cargo:rerun-if-changed=../../scripts/sync-sparkarc-config.mjs");
    let status = std::process::Command::new("node")
        .args(["../../scripts/sync-sparkarc-config.mjs", "--check"])
        .current_dir(std::env::var("CARGO_MANIFEST_DIR").expect("缺少 CARGO_MANIFEST_DIR"))
        .status()
        .expect("无法启动 Node.js 来校验 sparkarc.json 派生产物")
        .success();
    assert!(
        status,
        "sparkarc.json 派生产物已漂移，请运行 node scripts/sync-sparkarc-config.mjs。"
    );
    tauri_build::build();
}
