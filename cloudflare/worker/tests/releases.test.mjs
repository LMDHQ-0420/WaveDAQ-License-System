import assert from "node:assert/strict";
import test from "node:test";

import { platformAssetMatches, resolveGithubRelease, trustedGithubAsset } from "../src/releases.ts";

const repository = "LMDHQ-0420/WaveDAQ";
const release = {
  tag_name: "v1.2.3",
  assets: [
    { id: 101, name: "WaveDAQ-macos-arm64-v1.2.3.zip", url: `https://api.github.com/repos/${repository}/releases/assets/101`, digest: `sha256:${"a".repeat(64)}` },
    { id: 102, name: "WaveDAQ-macos-x64-v1.2.3.zip", url: `https://api.github.com/repos/${repository}/releases/assets/102`, digest: `sha256:${"b".repeat(64)}` },
    { id: 103, name: "WaveDAQ-windows-x64-v1.2.3.exe", url: `https://api.github.com/repos/${repository}/releases/assets/103`, digest: `sha256:${"c".repeat(64)}` }
  ]
};

test("matches each supported platform and rejects unsupported platforms", () => {
  assert.equal(platformAssetMatches(release.assets[0].name, "macos-arm64"), true);
  assert.equal(platformAssetMatches(release.assets[1].name, "macos-x64"), true);
  assert.equal(platformAssetMatches("WaveDAQ-mac-v1.2.3.zip", "macos-arm64"), true);
  assert.equal(platformAssetMatches("WaveDAQ-mac-v1.2.3.zip", "macos-x64"), true);
  assert.equal(platformAssetMatches(release.assets[2].name, "windows-x64"), true);
  assert.equal(platformAssetMatches(release.assets[2].name, "linux-x64"), false);
});

test("uses immutable GitHub asset IDs and correct launch targets", () => {
  const mac = resolveGithubRelease(repository, "wavedaq-8ch", release, "macos-arm64");
  const windows = resolveGithubRelease(repository, "wavedaq-8ch", release, "windows-x64");
  assert.equal(mac.id, "github-101");
  assert.equal(mac.version, "1.2.3");
  assert.equal(mac.launch_path, "@downloaded");
  assert.equal(windows.id, "github-103");
  assert.equal(windows.launch_path, "@downloaded");
});

test("rejects untrusted asset URLs and assets without a digest", () => {
  assert.equal(trustedGithubAsset(`https://api.github.com/repos/${repository}/releases/assets/101`, repository), true);
  assert.equal(trustedGithubAsset("https://example.com/malware", repository), false);
  assert.equal(resolveGithubRelease(repository, "wavedaq-8ch", { tag_name: "v1.0.0", assets: [{ ...release.assets[0], digest: null }] }, "macos-arm64"), null);
});
