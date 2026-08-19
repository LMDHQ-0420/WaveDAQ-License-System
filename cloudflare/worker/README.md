# Worker API

## 初始化

```bash
npm install
npx wrangler d1 create wavedaq-license
# 将返回的 database_id 写入 wrangler.toml
npx wrangler d1 migrations apply wavedaq-license --local
npx wrangler dev
```

生成签名密钥：

```bash
python3 ../../tools/generate_signing_key.py
```

生产环境使用 Secret 保存私钥，不要写入 `wrangler.toml`：

```bash
npx wrangler secret put LICENSE_SIGNING_PRIVATE_KEY
npx wrangler secret put ADMIN_TOKEN
```

核心 API：

```text
POST /api/activate
GET  /api/releases?license_id=...&device_id=...
GET  /api/admin/licenses
POST /api/admin/products
POST /api/admin/licenses
POST /api/admin/releases
```

撤销接口：

```text
POST /api/admin/licenses/:id/revoke
POST /api/admin/devices/:id/revoke
```

撤销会阻止后续在线 API 使用；已经签发且允许离线运行的授权，在其有效期/离线宽限期内仍可能继续运行，这是离线软件授权无法避免的取舍。

管理 API 使用 `Authorization: Bearer <ADMIN_TOKEN>`。生产环境还应在管理路径前配置 Cloudflare Access。
