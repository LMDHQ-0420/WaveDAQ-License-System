import { StrictMode, useState } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type License = { id: string; status: string; expires_at: string | null; offline_grace_days: number; created_at: string };
type Product = { id: string; name: string; description: string; status: string };
type Device = { id: string; fingerprint: string | null; status: string; last_seen_at: string | null };
type Release = { id: string; product_id: string; version: string; platform: string; sha256: string; file_name: string; launch_path: string; status: string };

function App() {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("尚未连接服务端");
  const [licenses, setLicenses] = useState<License[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [releases, setReleases] = useState<Release[]>([]);
  const [productForm, setProductForm] = useState({ id: "", name: "", description: "" });
  const [licenseForm, setLicenseForm] = useState({ activation_code: "", product_id: "", version_range: "*", platform: "windows-x64", offline_grace_days: "3650" });
  const [releaseForm, setReleaseForm] = useState({ id: "", product_id: "", version: "", platform: "windows-x64", asset_url: "", sha256: "", file_name: "", launch_path: "@downloaded" });

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`/api/admin${path}`, { ...init, headers: { "content-type": "application/json", authorization: `Bearer ${token}`, ...(init?.headers ?? {}) } });
    const data = await response.json() as T & { error?: string };
    if (!response.ok) throw new Error(data.error ?? "请求失败");
    return data;
  }

  async function loadAll() {
    const [licenseData, productData, deviceData, releaseData] = await Promise.all([
      api<{ licenses: License[] }>("/licenses"), api<{ products: Product[] }>("/products"), api<{ devices: Device[] }>("/devices"), api<{ releases: Release[] }>("/releases")
    ]);
    setLicenses(licenseData.licenses); setProducts(productData.products); setDevices(deviceData.devices); setReleases(releaseData.releases);
    setMessage("数据已刷新");
  }

  async function createProduct() {
    await api("/products", { method: "POST", body: JSON.stringify(productForm) });
    setProductForm({ id: "", name: "", description: "" }); await loadAll();
  }

  async function createLicense() {
    await api("/licenses", { method: "POST", body: JSON.stringify({ activation_code: licenseForm.activation_code, offline_grace_days: Number(licenseForm.offline_grace_days), products: [{ product_id: licenseForm.product_id, version_ranges: [licenseForm.version_range], platforms: [licenseForm.platform], features: [] }] }) });
    setLicenseForm({ ...licenseForm, activation_code: "" }); await loadAll();
  }

  async function createRelease() {
    await api("/releases", { method: "POST", body: JSON.stringify(releaseForm) });
    setReleaseForm({ ...releaseForm, id: "", version: "", asset_url: "", sha256: "", file_name: "" }); await loadAll();
  }

  async function revoke(kind: "licenses" | "devices", id: string) {
    if (!confirm(`确定撤销 ${id}？`)) return;
    await api(`/${kind}/${encodeURIComponent(id)}/revoke`, { method: "POST" }); await loadAll();
  }

  const run = (work: () => Promise<void>) => void work().catch((error: Error) => setMessage(error.message));
  return <main>
    <header><div><p className="eyebrow">WAVEDAQ</p><h1>License Console</h1></div><span className="status">{message}</span></header>
    <section className="card auth"><label>管理员 Token<input type="password" value={token} onChange={(event) => setToken(event.target.value)} /></label><button onClick={() => run(loadAll)}>刷新全部</button></section>

    <section className="grid">
      <article className="card"><h2>新增产品</h2><input placeholder="产品 ID，例如 wavedaq-8ch" value={productForm.id} onChange={(e) => setProductForm({ ...productForm, id: e.target.value })} /><input placeholder="产品名称" value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} /><input placeholder="说明" value={productForm.description} onChange={(e) => setProductForm({ ...productForm, description: e.target.value })} /><button onClick={() => run(createProduct)}>创建产品</button></article>
      <article className="card"><h2>新增授权</h2><div className="inline"><input placeholder="一次性激活码" value={licenseForm.activation_code} onChange={(e) => setLicenseForm({ ...licenseForm, activation_code: e.target.value.toUpperCase() })} /><button className="small" onClick={() => setLicenseForm({ ...licenseForm, activation_code: generateCode() })}>生成</button></div><select value={licenseForm.product_id} onChange={(e) => setLicenseForm({ ...licenseForm, product_id: e.target.value })}><option value="">选择产品</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select><input placeholder="版本范围，例如 1.0.*" value={licenseForm.version_range} onChange={(e) => setLicenseForm({ ...licenseForm, version_range: e.target.value })} /><select value={licenseForm.platform} onChange={(e) => setLicenseForm({ ...licenseForm, platform: e.target.value })}><option>windows-x64</option><option>macos-arm64</option><option>macos-x64</option></select><input type="number" placeholder="离线天数" value={licenseForm.offline_grace_days} onChange={(e) => setLicenseForm({ ...licenseForm, offline_grace_days: e.target.value })} /><button onClick={() => run(createLicense)}>创建授权</button></article>
      <article className="card"><h2>登记版本</h2><input placeholder="版本记录 ID" value={releaseForm.id} onChange={(e) => setReleaseForm({ ...releaseForm, id: e.target.value })} /><select value={releaseForm.product_id} onChange={(e) => setReleaseForm({ ...releaseForm, product_id: e.target.value })}><option value="">选择产品</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select><input placeholder="版本，例如 1.0.0" value={releaseForm.version} onChange={(e) => setReleaseForm({ ...releaseForm, version: e.target.value })} /><select value={releaseForm.platform} onChange={(e) => setReleaseForm({ ...releaseForm, platform: e.target.value })}><option>windows-x64</option><option>macos-arm64</option><option>macos-x64</option></select><input placeholder="安装包文件名" value={releaseForm.file_name} onChange={(e) => setReleaseForm({ ...releaseForm, file_name: e.target.value })} /><input placeholder="启动路径，便携版填 @downloaded" value={releaseForm.launch_path} onChange={(e) => setReleaseForm({ ...releaseForm, launch_path: e.target.value })} /><input placeholder="GitHub Asset API URL" value={releaseForm.asset_url} onChange={(e) => setReleaseForm({ ...releaseForm, asset_url: e.target.value })} /><input placeholder="SHA-256" value={releaseForm.sha256} onChange={(e) => setReleaseForm({ ...releaseForm, sha256: e.target.value })} /><button onClick={() => run(createRelease)}>登记版本</button></article>
    </section>

    <Table title="授权" headers={["ID", "状态", "离线天数", "过期时间", "操作"]} rows={licenses.map((item) => [item.id, item.status, String(item.offline_grace_days), item.expires_at ?? "永久", item.status !== "revoked" ? <button className="danger" onClick={() => run(() => revoke("licenses", item.id))}>撤销</button> : "-"])} />
    <Table title="设备" headers={["ID", "指纹", "状态", "最后在线", "操作"]} rows={devices.map((item) => [item.id, item.fingerprint ?? "-", item.status, item.last_seen_at ?? "-", item.status !== "revoked" ? <button className="danger" onClick={() => run(() => revoke("devices", item.id))}>撤销</button> : "-"])} />
    <Table title="产品" headers={["ID", "名称", "状态"]} rows={products.map((item) => [item.id, item.name, item.status])} />
    <Table title="版本" headers={["ID", "产品", "版本", "平台", "文件", "状态"]} rows={releases.map((item) => [item.id, item.product_id, item.version, item.platform, item.file_name, item.status])} />
  </main>;
}

function generateCode(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(20));
  return Array.from({ length: 4 }, (_, group) => Array.from({ length: 5 }, (_, index) => alphabet[bytes[group * 5 + index] % alphabet.length]).join("")).join("-");
}

function Table({ title, headers, rows }: { title: string; headers: string[]; rows: ReactNode[][] }) {
  return <section className="card"><div className="section-title"><h2>{title}</h2><span>{rows.length}</span></div><table><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table>{rows.length === 0 && <p className="empty">暂无数据</p>}</section>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
