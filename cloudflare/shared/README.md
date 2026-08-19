# Shared Protocols

保存 Launcher 与 Cloudflare 共同使用的授权文件、产品型号和版本清单数据结构定义。

## License 文件规则

`license-schema.json` 定义授权文件格式。`signature` 字段不参与签名；签名输入是删除 `signature` 后的 JSON 对象，使用固定的规范化 JSON 序列化后，以 UTF-8 编码交给 Ed25519 签名。

规范化规则：

1. 删除顶层 `signature` 字段；
2. 对所有对象键按字典序递归排序；
3. 数组保持原顺序；
4. JSON 使用 UTF-8、无空白字符、不得追加换行；
5. 签名和公钥使用 base64url 编码且不带 `=` 填充。

启动器和真实 WaveDAQ 都必须验证服务器签名、本机设备私钥对应的公钥、产品 ID、版本范围、平台和有效期。
