import { execSync } from "child_process";
import { rmSync, unlinkSync, existsSync } from "fs";
import { join } from "path";

async function globalTeardown() {
  const projectRoot = join(__dirname, "..", "..");

  console.log("Stopping E2E server...");
  try {
    execSync("devenv processes down --no-tui", {
      cwd: projectRoot,
      timeout: 60_000,
      stdio: "inherit",
    });
  } catch (e) {
    console.warn("Failed to stop devenv processes:", e);
  }

  const pid = process.env.BARK_E2E_PID;
  if (pid) {
    try {
      process.kill(Number(pid), "SIGTERM");
    } catch {
      // Already dead
    }
  }

  // Clean up .env.e2e
  const envPath = join(projectRoot, ".env.e2e");
  if (existsSync(envPath)) {
    unlinkSync(envPath);
  }

  // Clean up temp data directory
  const dataDir = process.env.BARK_E2E_DATA_DIR;
  if (dataDir) {
    console.log(`Cleaning up ${dataDir}`);
    try {
      rmSync(dataDir, { recursive: true, force: true });
    } catch (e) {
      console.warn(`Failed to clean up ${dataDir}:`, e);
    }
  }

  console.log("E2E teardown complete");
}

export default globalTeardown;
