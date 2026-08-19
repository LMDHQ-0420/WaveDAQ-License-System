# Cloudflare License Service

包含 Cloudflare Worker API、D1 数据库迁移和管理后台。管理网站构建后作为 Worker 静态资源提供，管理 API 和网页使用同一个域名。

部署顺序：

```bash
cd admin && npm install && npm run build
cd ../worker && npm install && npx wrangler deploy
```

也可以从本目录执行：

```bash
npm run install:all
npm run deploy
```
