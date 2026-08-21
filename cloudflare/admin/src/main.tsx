import { StrictMode, useState } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Product = { id: string; name: string; description: string; github_repository: string; status: string; is_frozen: number };
type License = { id: string; name: string; status: string; is_frozen: number; term: string; expires_at: string | null; created_at: string; has_code: number; product_names: string | null; activated_at: string | null; device_ids: string | null; first_bound_at: string | null };
type Device = { id: string; fingerprint: string | null; status: string; last_seen_at: string | null };

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("尚未连接服务端");
  const [products, setProducts] = useState<Product[]>([]);
  const [licenses, setLicenses] = useState<License[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [productForm, setProductForm] = useState({ product_id: "", name: "", github_repository_url: "", description: "" });
  const [licenseForm, setLicenseForm] = useState({ name: "", activation_code: "", product_ids: [] as string[], term: "永久授权", expires_at: "" });
  const [productEditor, setProductEditor] = useState<{ item: Product; repository: string; description: string } | null>(null);
  const [licenseEditor, setLicenseEditor] = useState<{ item: License; term: string; expires_at: string } | null>(null);
  const [codeViewer, setCodeViewer] = useState<{ name: string; code: string } | null>(null);
  const [codeCopied, setCodeCopied] = useState(false);

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`/api/admin${path}`, { credentials: "same-origin", ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
    const data = await response.json() as T & { error?: string };
    if (!response.ok) { if (response.status === 401) setAuthenticated(false); throw new Error(data.error ?? "请求失败"); }
    return data;
  }

  async function login() {
    const response = await fetch("/api/admin/login", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify({ password }) });
    const data = await response.json() as { error?: string };
    if (!response.ok) throw new Error(data.error ?? "登录失败");
    setPassword(""); setAuthenticated(true); window.history.replaceState({}, "", "/"); await loadAll();
  }

  async function logout() {
    await fetch("/api/admin/logout", { method: "POST", credentials: "same-origin" });
    setAuthenticated(false);
  }

  async function loadAll() {
    const [productData, licenseData, deviceData] = await Promise.all([
      api<{ products: Product[] }>("/products"), api<{ licenses: License[] }>("/licenses"), api<{ devices: Device[] }>("/devices")
    ]);
    setProducts(productData.products); setLicenses(licenseData.licenses); setDevices(deviceData.devices);
    setMessage("数据已刷新");
  }

  async function createProduct() {
    await api("/products", { method: "POST", body: JSON.stringify(productForm) });
    setProductForm({ product_id: "", name: "", github_repository_url: "", description: "" }); await loadAll();
  }

  async function createLicense() {
    if (!licenseForm.product_ids.length) throw new Error("请至少选择一个产品");
    const expiresAt = licenseForm.expires_at ? new Date(licenseForm.expires_at).toISOString() : null;
    await api("/licenses", { method: "POST", body: JSON.stringify({ ...licenseForm, expires_at: expiresAt }) });
    setLicenseForm({ name: "", activation_code: "", product_ids: [], term: "永久授权", expires_at: "" }); await loadAll();
  }

  function editProduct(item: Product) {
    setProductEditor({ item, repository: `https://github.com/${item.github_repository}`, description: item.description });
  }

  async function saveProductEdit() {
    if (!productEditor) return;
    await api(`/products/${encodeURIComponent(productEditor.item.id)}`, { method: "PATCH", body: JSON.stringify({ github_repository_url: productEditor.repository, description: productEditor.description }) });
    setProductEditor(null); await loadAll();
  }

  async function deleteProduct(item: Product) {
    if (!confirm(`确定删除产品“${item.name}”？已有历史记录时会保留历史并标记为已删除。`)) return;
    await api(`/products/${encodeURIComponent(item.id)}`, { method: "DELETE" }); await loadAll();
  }

  async function toggleProduct(item: Product) {
    const action = item.is_frozen ? "unfreeze" : "freeze";
    if (!confirm(`${action === "freeze" ? "冻结" : "解冻"}产品“${item.name}”？`)) return;
    await api(`/products/${encodeURIComponent(item.id)}/${action}`, { method: "POST" }); await loadAll();
  }

  function editLicense(item: License) {
    setLicenseEditor({ item, term: item.term === "永久" ? "永久授权" : item.term, expires_at: toDateTimeLocal(item.expires_at) });
  }

  async function saveLicenseEdit() {
    if (!licenseEditor) return;
    const expiresAt = licenseEditor.term === "永久授权" ? null : new Date(licenseEditor.expires_at).toISOString();
    await api(`/licenses/${encodeURIComponent(licenseEditor.item.id)}`, { method: "PATCH", body: JSON.stringify({ term: licenseEditor.term, expires_at: expiresAt }) });
    setLicenseEditor(null); await loadAll();
  }

  async function toggleLicense(item: License) {
    const action = item.is_frozen ? "unfreeze" : "freeze";
    if (!confirm(`${action === "freeze" ? "冻结" : "解冻"}此授权？`)) return;
    await api(`/licenses/${encodeURIComponent(item.id)}/${action}`, { method: "POST" }); await loadAll();
  }

  async function viewLicenseCode(item: License) {
    const result = await api<{ activation_code: string }>(`/licenses/${encodeURIComponent(item.id)}/code`);
    setCodeCopied(false); setCodeViewer({ name: item.name || "未命名", code: result.activation_code });
  }

  async function copyLicenseCode() {
    if (!codeViewer) return;
    await navigator.clipboard.writeText(codeViewer.code);
    setCodeCopied(true);
  }

  async function revokeLicense(id: string) {
    if (!confirm(`确定撤销此授权？撤销记录会保留，且不能重新激活。`)) return;
    await api(`/licenses/${encodeURIComponent(id)}/revoke`, { method: "POST" }); await loadAll();
  }

  async function unbindDevice(id: string) {
    if (!confirm(`确定解绑此设备？有效授权会恢复为未使用；撤销授权的历史绑定会保留。`)) return;
    await api(`/devices/${encodeURIComponent(id)}/unbind`, { method: "POST" }); await loadAll();
  }

  const run = (work: () => Promise<void>) => void work().catch((error: Error) => setMessage(error.message));
  if (!authenticated) return <main className="login-page">
    <header><div><p className="eyebrow">WAVEDAQ</p><h1>License Console</h1></div></header>
    <section className="card login-card"><h2>管理员登录</h2><p className="login-hint">请输入管理员密码进入授权管理界面。</p><form onSubmit={(event) => { event.preventDefault(); run(login); }}><input autoFocus type="password" placeholder="管理员密码" value={password} onChange={(event) => setPassword(event.target.value)} /><button type="submit">登录</button></form>{message !== "尚未连接服务端" && <p className="error">{message}</p>}</section>
    <p className="credit">Coding by sunyuxiang25@mails.ucas.edu.cn</p>
  </main>;
  return <main>
    <header><div><p className="eyebrow">WAVEDAQ</p><h1>License Console</h1></div><div className="header-actions"><span className="status">{message}</span><button className="secondary" onClick={logout}>退出登录</button></div></header>
    <section className="toolbar"><span>授权管理</span><button onClick={() => run(loadAll)}>刷新全部</button></section>

    <section className="grid">
      <section className="card form-card"><h2>新增产品</h2><p className="form-hint">产品 ID 是授权协议中的固定标识，名称可以用于展示；GitHub 仓库用于查找最新 Release。</p><label>产品 ID<input placeholder="例如 wavedaq-8ch" value={productForm.product_id} onChange={(e) => setProductForm({ ...productForm, product_id: e.target.value.toLowerCase() })} /></label><label>产品名称<input value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} /></label><label>GitHub 仓库链接<input placeholder="https://github.com/owner/repository" value={productForm.github_repository_url} onChange={(e) => setProductForm({ ...productForm, github_repository_url: e.target.value })} /></label><label>说明<input value={productForm.description} onChange={(e) => setProductForm({ ...productForm, description: e.target.value })} /></label><button onClick={() => run(createProduct)}>创建产品</button></section>
      <section className="card form-card"><h2>生成激活码</h2><label>激活码名称<input placeholder="客户名称或用途" value={licenseForm.name} onChange={(e) => setLicenseForm({ ...licenseForm, name: e.target.value })} /></label><div className="inline"><input placeholder="激活码" value={licenseForm.activation_code} onChange={(e) => setLicenseForm({ ...licenseForm, activation_code: e.target.value.toUpperCase() })} /><button className="small" onClick={() => setLicenseForm({ ...licenseForm, activation_code: generateCode() })}>生成</button></div><label>授权产品<div className="checks">{products.filter((product) => product.status === "active" && !product.is_frozen).map((product) => <label className="check" key={product.id}><input type="checkbox" checked={licenseForm.product_ids.includes(product.id)} onChange={(e) => setLicenseForm({ ...licenseForm, product_ids: e.target.checked ? [...licenseForm.product_ids, product.id] : licenseForm.product_ids.filter((id) => id !== product.id) })} />{product.name}</label>)}</div></label><label>授权期限<select value={licenseForm.term} onChange={(e) => setLicenseForm({ ...licenseForm, term: e.target.value })}><option>永久授权</option><option>自定义</option></select></label>{licenseForm.term === "自定义" && <label>过期时间<input type="datetime-local" value={licenseForm.expires_at} onChange={(e) => setLicenseForm({ ...licenseForm, expires_at: e.target.value })} /></label>}<button onClick={() => run(createLicense)}>创建激活码</button></section>
    </section>

    <Table title="产品" headers={["产品 ID", "名称", "GitHub 仓库", "说明", "状态", "创建时间", "操作"]} rows={products.map((item) => [item.id, item.name, item.github_repository, item.description || "-", statusLabel(item.status, item.is_frozen, "product"), item.created_at, item.status !== "disabled" ? <><button className="small" onClick={() => editProduct(item)}>修改</button> <button className="secondary small" onClick={() => run(() => toggleProduct(item))}>{item.is_frozen ? "解冻" : "冻结"}</button> <button className="danger small" onClick={() => run(() => deleteProduct(item))}>删除</button></> : "-"])} />
    <Table title="激活码 / 授权" headers={["名称", "产品", "状态", "授权期限", "过期时间", "激活时间", "绑定设备", "首次绑定", "操作"]} rows={licenses.map((item) => [item.name || "未命名", item.product_names ?? "-", statusLabel(item.status, item.is_frozen, "license"), item.term === "永久" ? "永久授权" : item.term, item.expires_at ?? "永久", item.activated_at ?? "未激活", item.device_ids ?? "未绑定", item.first_bound_at ?? "-", <><button className="small" onClick={() => run(() => viewLicenseCode(item))}>查看</button>{item.status !== "revoked" ? <> <button className="small" onClick={() => editLicense(item)}>修改</button> <button className="secondary small" onClick={() => run(() => toggleLicense(item))}>{item.is_frozen ? "解冻" : "冻结"}</button> <button className="danger small" onClick={() => run(() => revokeLicense(item.id))}>撤销</button></> : <> -</>}</>])} />
    <Table title="设备" headers={["ID", "指纹", "状态", "最后在线", "操作"]} rows={devices.map((item) => [item.id, item.fingerprint ?? "-", item.status, item.last_seen_at ?? "-", <button className="danger" onClick={() => run(() => unbindDevice(item.id))}>解绑</button>])} />
    {productEditor && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setProductEditor(null); }}><section className="modal card" role="dialog" aria-modal="true" aria-labelledby="product-edit-title"><div className="modal-title"><h2 id="product-edit-title">修改产品</h2><button className="icon-button" onClick={() => setProductEditor(null)} aria-label="关闭">×</button></div><p className="form-hint">产品名称：{productEditor.item.name}（不可修改）</p><label>GitHub 仓库链接<input value={productEditor.repository} onChange={(event) => setProductEditor({ ...productEditor, repository: event.target.value })} /></label><label>产品说明<textarea value={productEditor.description} onChange={(event) => setProductEditor({ ...productEditor, description: event.target.value })} maxLength={500} /></label><div className="modal-actions"><button className="secondary" onClick={() => setProductEditor(null)}>取消</button><button onClick={() => run(saveProductEdit)}>保存修改</button></div></section></div>}
    {licenseEditor && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setLicenseEditor(null); }}><section className="modal card" role="dialog" aria-modal="true" aria-labelledby="license-edit-title"><div className="modal-title"><h2 id="license-edit-title">修改授权</h2><button className="icon-button" onClick={() => setLicenseEditor(null)} aria-label="关闭">×</button></div><p className="form-hint">授权名称：{licenseEditor.item.name || "未命名"}。授权已经激活也可以修改。</p><label>授权期限<select value={licenseEditor.term} onChange={(event) => setLicenseEditor({ ...licenseEditor, term: event.target.value, expires_at: event.target.value === "永久授权" ? "" : licenseEditor.expires_at })}><option>永久授权</option><option>自定义</option></select></label>{licenseEditor.term === "自定义" && <label>过期时间<input type="datetime-local" value={licenseEditor.expires_at} onChange={(event) => setLicenseEditor({ ...licenseEditor, expires_at: event.target.value })} required /></label>}<div className="modal-actions"><button className="secondary" onClick={() => setLicenseEditor(null)}>取消</button><button onClick={() => run(saveLicenseEdit)}>保存修改</button></div></section></div>}
    {codeViewer && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setCodeViewer(null); }}><section className="modal card" role="dialog" aria-modal="true" aria-labelledby="code-view-title"><div className="modal-title"><h2 id="code-view-title">查看激活码</h2><button className="icon-button" onClick={() => setCodeViewer(null)} aria-label="关闭">×</button></div><p className="form-hint">授权名称：{codeViewer.name}</p><input className="code-display" value={codeViewer.code} readOnly /><div className="modal-actions"><button className="secondary" onClick={() => setCodeViewer(null)}>关闭</button><button onClick={() => run(copyLicenseCode)}>{codeCopied ? "已复制" : "复制激活码"}</button></div></section></div>}
    <p className="credit">Coding by sunyuxiang25@mails.ucas.edu.cn</p>
  </main>;
}

function toDateTimeLocal(value: string | null): string {
  return value ? new Date(value).toISOString().slice(0, 16) : "";
}

function statusLabel(status: string, frozen: number, kind: "product" | "license"): string {
  if (frozen) return "冻结";
  if (kind === "product") return status === "active" ? "启用" : "已删除";
  return status === "unused" ? "未使用" : status === "active" ? "已激活" : "已撤销";
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
