import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type License = { id: string; status: string; expires_at: string | null; created_at: string };

function App() {
  const [token, setToken] = useState("");
  const [licenses, setLicenses] = useState<License[]>([]);
  const [message, setMessage] = useState("尚未连接服务端");

  async function loadLicenses() {
    const response = await fetch("/api/admin/licenses", { headers: { authorization: `Bearer ${token}` } });
    const data = await response.json() as { licenses?: License[]; error?: string };
    if (!response.ok) throw new Error(data.error ?? "请求失败");
    setLicenses(data.licenses ?? []);
    setMessage(`已加载 ${data.licenses?.length ?? 0} 个授权`);
  }

  return <main>
    <header><div><p className="eyebrow">WAVEDAQ</p><h1>License Console</h1></div><span className="status">{message}</span></header>
    <section className="card auth"><label>管理员 Token<input type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="由 Cloudflare Access 或部署密钥保护" /></label><button onClick={() => void loadLicenses().catch((error: Error) => setMessage(error.message))}>刷新</button></section>
    <section className="card"><div className="section-title"><h2>授权列表</h2><span>{licenses.length}</span></div><table><thead><tr><th>ID</th><th>状态</th><th>过期时间</th><th>创建时间</th></tr></thead><tbody>{licenses.map((license) => <tr key={license.id}><td>{license.id}</td><td><b className={`badge ${license.status}`}>{license.status}</b></td><td>{license.expires_at ?? "永久"}</td><td>{license.created_at}</td></tr>)}</tbody></table>{licenses.length === 0 && <p className="empty">输入管理员 Token 后加载授权。</p>}</section>
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
