export interface GithubAsset { id: number; name: string; url: string; digest?: string | null; }
export interface GithubRelease { tag_name: string; assets: GithubAsset[]; }
export interface ResolvedRelease { id: string; product_id: string; version: string; platform: string; asset_url: string; sha256: string; file_name: string; launch_path: string; }

export function trustedGithubAsset(value: string, repository: string): boolean {
  try {
    const url = new URL(value);
    const assetId = url.pathname.split("/").pop() ?? "";
    return url.protocol === "https:" && url.hostname === "api.github.com" && url.pathname === `/repos/${repository}/releases/assets/${assetId}` && /^[0-9]+$/.test(assetId);
  } catch {
    return false;
  }
}

export function platformAssetMatches(name: string, platform: string): boolean {
  const value = name.toLowerCase();
  const isMac = /(mac|darwin|osx)/.test(value);
  const isArm = /(arm64|aarch64|apple[-_ ]?silicon)/.test(value);
  const isX64 = /(x64|x86_64|amd64|intel)/.test(value);
  if (platform === "macos-arm64") return isMac && (isArm || !isX64);
  if (platform === "macos-x64") return isMac && (isX64 || !isArm);
  if (platform === "windows-x64") return /(windows|win).*(x64|x86_64|amd64)|(x64|x86_64|amd64).*(windows|win)/.test(value);
  return false;
}

export function resolveGithubRelease(repository: string, productId: string, release: GithubRelease, platform: string): ResolvedRelease | null {
  const asset = release.assets.find((item) => platformAssetMatches(item.name, platform) && item.digest?.toLowerCase().startsWith("sha256:"));
  if (!asset || !asset.digest) return null;
  if (!trustedGithubAsset(asset.url, repository)) throw new Error("GitHub 版本地址不可信");
  return {
    id: `github-${asset.id}`,
    product_id: productId,
    version: release.tag_name.replace(/^v/, ""),
    platform,
    asset_url: asset.url,
    sha256: asset.digest.slice("sha256:".length),
    file_name: asset.name,
    launch_path: "@downloaded"
  };
}
