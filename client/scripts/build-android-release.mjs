import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { delimiter, dirname, join } from "node:path";

function run(command, args, env, stdio = "inherit") {
  return spawnSync(command, args, {
    cwd: process.cwd(),
    env,
    stdio,
    shell: false,
  });
}

function canBuildOpenSsl(env) {
  const result = run("perl", ["-MLocale::Maketext::Simple", "-e", "exit 0"], env, "ignore");
  return !result.error && result.status === 0;
}

function perlCandidates() {
  const candidates = [];
  const add = (base, ...parts) => {
    if (base) candidates.push(join(base, ...parts));
  };

  add(process.env.ProgramFiles, "Git", "usr", "bin", "perl.exe");
  add(process.env["ProgramFiles(x86)"], "Git", "usr", "bin", "perl.exe");
  add(process.env.LOCALAPPDATA, "Programs", "Git", "usr", "bin", "perl.exe");
  add(process.env.SCOOP, "apps", "perl", "current", "perl", "bin", "perl.exe");
  add(process.env.SCOOP, "apps", "git", "current", "usr", "bin", "perl.exe");
  add(process.env.USERPROFILE, "scoop", "apps", "perl", "current", "perl", "bin", "perl.exe");
  add(process.env.USERPROFILE, "scoop", "apps", "git", "current", "usr", "bin", "perl.exe");
  add(process.env.SystemDrive, "Strawberry", "perl", "bin", "perl.exe");

  return candidates;
}

function withPerlOnPath() {
  const env = { ...process.env };
  if (canBuildOpenSsl(env)) return env;

  const pathKey = Object.keys(env).find((key) => key.toLowerCase() === "path") ?? "PATH";
  for (const perl of perlCandidates()) {
    if (!existsSync(perl)) continue;

    const candidateEnv = {
      ...env,
      [pathKey]: `${dirname(perl)}${delimiter}${env[pathKey] ?? ""}`,
    };
    if (canBuildOpenSsl(candidateEnv)) {
      console.log(`Using Perl: ${perl}`);
      return candidateEnv;
    }
  }

  throw new Error(
    "A complete Perl installation was not found. Install Strawberry Perl with Locale::Maketext::Simple, then retry the Android release build.",
  );
}

try {
  const env = process.platform === "win32" ? withPerlOnPath() : process.env;
  const tauriCli = join(process.cwd(), "node_modules", "@tauri-apps", "cli", "tauri.js");
  const result = run(
    process.execPath,
    [tauriCli, "android", "build", "--apk", "--target", "aarch64"],
    env,
  );

  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[android-release] ERROR: ${message}`);
  process.exitCode = 1;
}
