<p align="center">
  <img src="logo.png" width="120" alt="License System Logo"/>
</p>

<h1 align="center">WaveDAQ License System</h1>
<p align="center">Licensing, distribution, and offline verification for desktop software</p>
<p align="center"><a href="README.md">中文</a> | <strong>English</strong></p>
<p align="center"><a href="https://github.com/LMDHQ-0420/WaveDAQ-License-System/releases">Download</a> · <a href="#technical-report">Technical Report</a></p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/PySide6-Qt-41CD52?logo=qt" alt="PySide6"/>
  <img src="https://img.shields.io/badge/Cloudflare-Workers-F38020?logo=cloudflare&logoColor=white" alt="Cloudflare Workers"/>
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey" alt="Platforms"/>
</p>

WaveDAQ License System is a licensing, distribution, and offline verification system for multiple desktop applications. Administrators register products and GitHub repositories. Users activate their device, install products, and launch them through one Launcher.

## User Guide

### 1. Download the verification software

Download the appropriate WaveDAQ-Launcher package from [GitHub Releases](https://github.com/LMDHQ-0420/WaveDAQ-License-System/releases), extract it, and launch the graphical application.

### 2. Get an activation code

Activation codes are created and distributed by the administrator. To request a code, check an authorized product, or handle device binding, contact:

**sunyuxiang25@mails.ucas.edu.cn**

### 3. Activate and use a product

1. Launch WaveDAQ-Launcher.
2. Enter the activation code and submit the device authorization request.
3. After activation, the Launcher displays the authorized products.
4. Select a product and install or launch it.
5. The Launcher matches the GitHub Release asset for the current platform and verifies its SHA-256 digest.
6. Launch the installed product from the Launcher.

The first activation requires an Internet connection. After activation, the signed license is stored locally and the product can start offline. When online again, the Launcher can synchronize the license state and product information.

One activation code can be bound to one device. Contact the administrator to unbind the old device before moving to another computer. License terms support permanent authorization and custom expiration dates.

### 4. Install from source

Python 3.11, Conda, and a network connection are required:

```
git clone https://github.com/LMDHQ-0420/WaveDAQ-License-System.git
cd WaveDAQ-License-System
conda create -n WaveDAQLaucher python=3.11 -y
conda activate WaveDAQLaucher
pip install -r launcher/requirements.txt
python launcher/src/main.py
```

Source execution uses the Worker URL and server public key in `launcher/src/config.py` and is intended for development and testing.

### 5. Frequently asked questions

#### 1. Where can I get an activation code?

Contact sunyuxiang25@mails.ucas.edu.cn and provide the product and operating system you need.

#### 2. Why is an Internet connection required for activation?

The server checks the activation code, authorized products, expiration, and device binding before issuing a signed license. Internet access is not required every time the product starts after the first activation.

#### 3. Can one activation code be used on two computers?

No. One activation code can be bound to only one device. Contact the administrator to unbind it before moving to another computer.

#### 4. Can the product be used offline?

Yes. After the first activation, the Launcher and product verify the signed license locally. A custom expiration date is still enforced offline.

#### 5. Why is a product missing?

The product must be registered by the administrator and included in the current activation code.

#### 6. What are the Launcher and the product?

The Launcher is the unified authorization, installation, and launch entry point. The product is the desktop application that provides the actual functions. One Launcher can manage multiple products.

#### 7. How do I report a problem?

Send the operating system, Launcher message, product name, and reproduction steps to sunyuxiang25@mails.ucas.edu.cn. Do not submit device private keys, administrator passwords, or GitHub Tokens.

## Technical Report

### 1. Data flow

```
Data Flow/
├── Administrator Console
│   ├── Product name, product ID, and GitHub repository
│   │   └── Write → Cloudflare D1
│   └── Activation code, license term, and authorized products
│       └── Write → Cloudflare D1
├── User launches Launcher
│   ├── Activation code, device ID, and device public key
│   │   └── Request → Cloudflare Worker
│   │       └── Check license and device binding → Cloudflare D1
│   │           └── Return Ed25519-signed license → Launcher
│   └── Save license and device information
│       └── Write → Local WaveDAQ-Launcher data directory
├── Launcher checks products
│   └── Request latest Release → Cloudflare Worker
│       └── Read latest Release → Product GitHub repository
│           └── Return platform asset, version, and SHA-256 → Launcher
├── Launcher downloads a product
│   └── Download request → Cloudflare Worker
│       └── Read and verify latest GitHub asset again → GitHub
│           └── Proxy package → Launcher
│               └── Verify SHA-256, save, install, and launch → Local product
└── Product starts
    ├── Read local license and device key → Local data directory
    └── Verify signature, product ID, platform, and term offline → Product startup
```

The three parts are the WaveDAQ-Launcher, independent product repositories, and the Cloudflare authorization service. Release versions belong to GitHub Releases and are not part of license configuration. The Worker reads the latest Release and matches `macos-arm64`, `macos-x64`, or `windows-x64` assets.

### 2. Project structure

```
WaveDAQ-License-System/
├── .github/workflows/build-launcher.yml # Launcher release workflow
├── launcher/                            # WaveDAQ-Launcher
│   ├── src/main.py                      # GUI entry point
│   ├── src/gui.py                       # Activation, product, download, and launch UI
│   ├── src/api_client.py                # API requests
│   ├── src/config.py                    # Worker URL and public key
│   ├── src/device_identity.py           # Device Ed25519 key and system keyring
│   ├── src/license_verifier.py          # Launcher license verification
│   ├── src/local_storage.py             # License, catalog, and installation records
│   ├── src/release_downloader.py        # Download and SHA-256 verification
│   ├── src/software_installer.py        # Installer opening and product launch
│   ├── tests/                           # Launcher tests
│   └── Launcher.spec                    # PyInstaller configuration
├── license_sdk/                         # Offline verification module for products
│   ├── __init__.py
│   ├── config.py                        # Product ID and server public key
│   └── verifier.py                      # Signature, device, term, and platform checks
├── cloudflare/
│   ├── package.json                     # Cloudflare project scripts
│   ├── worker/                          # Worker API and D1 migrations
│   ├── admin/                           # React administrator console
│   ├── shared/license-schema.json       # Offline license document schema
│   └── tools/                           # Key, activation code, and password tools
├── .gitignore
├── logo.png
└── README.md
```

Products such as WaveDAQ are maintained in independent repositories. A product only needs to copy `license_sdk`.

### 3. D1 database structure

| Table | Purpose | Main fields |
|---|---|---|
| products | Product catalog | `id`, `name`, `description`, `github_repository`, `status`, `is_frozen`, `created_at` |
| licenses | Activation codes and license state | `id`, `name`, `code_hash`, `code_ciphertext`, `status`, `term`, `expires_at`, `is_frozen`, `created_at` |
| license_products | License-to-product relationship | `license_id`, `product_id` |
| devices | Device identity | `id`, `public_key`, `fingerprint`, `status`, `created_at`, `last_seen_at` |
| activations | Activation-to-device binding | `license_id`, `device_id`, `activated_at` |
| request_nonces | Request replay protection | `nonce`, `device_id`, `created_at` |
| admin_login_attempts | Administrator login rate limiting | `client_hash`, `failures`, `first_failed_at`, `last_failed_at`, `blocked_until` |

Product versions, platform assets, and SHA-256 digests are resolved directly from the latest GitHub Release at request time and are not stored in D1.

### 4. Public API

Device requests use these headers:

```
x-device-id
x-device-timestamp
x-device-nonce
x-device-signature
```

The signed message is:

```
{HTTP_METHOD}\\n{PATH}\\n{license_id}\\n{device_id}\\n{timestamp}\\n{nonce}
```

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/activate` | Activate one device with an activation code |
| GET | `/api/releases?license_id=lic_xxx` | Get authorized products and the latest platform assets |
| POST | `/api/license/refresh?license_id=lic_xxx` | Refresh the signed license |
| GET | `/api/download/{release_id}?license_id=lic_xxx&product_id=product_xxx&platform=macos-arm64` | Verify and proxy the latest package |
| POST | `/api/admin/login` | Administrator login |
| POST/GET/PATCH/DELETE | `/api/admin/...` | Product, license, and device management |

Administrator endpoints use the HttpOnly session cookie returned by `/api/admin/login`. They include product creation and editing, activation-code creation and viewing, license-term editing, revoke/freeze operations, and device unbinding.

### 5. Configure your own Cloudflare service

```bash
cd cloudflare/worker
npm install
npx wrangler login
npx wrangler d1 create your-license-database
```

Put the database ID, database name, and Worker name in `cloudflare/worker/wrangler.toml`. Then configure the Secrets:

```bash
python ../tools/generate_signing_key.py
npx wrangler secret put LICENSE_SIGNING_PRIVATE_KEY
python ../tools/set_admin_password.py
npx wrangler secret put ADMIN_PASSWORD_HASH
openssl rand -hex 32
npx wrangler secret put ADMIN_TOKEN
npx wrangler secret put GITHUB_TOKEN
```

Keep the signing private key, administrator password hash, administrator token, and GitHub Token in Cloudflare Secrets only. Put the signing public key in `launcher/src/config.py` and each product's `license_sdk/config.py`.

Build the administrator console, apply migrations, and deploy:

```bash
cd cloudflare/admin
npm install
npm run build
cd ../worker
npx wrangler d1 migrations apply your-license-database --remote
npx wrangler deploy
```

Put the deployed Worker URL in `launcher/src/config.py` as `API_URL`, then rebuild the Launcher and products. Local development uses `cloudflare/worker/.dev.vars` and `npx wrangler dev`.

### 6. Runtime directories

The Launcher and products share the `WaveDAQ-Launcher` user data directory:

```
macOS:  ~/Library/Application Support/WaveDAQ-Launcher/
Windows: %APPDATA%\\WaveDAQ-Launcher\\
Linux:   ~/.config/WaveDAQ-Launcher/
```

The directory contains `device.json`, `license.json`, `licenses/`, `catalogs/`, `installations.json`, `downloads/`, and `revoked_licenses.json`. Packages are stored at `<data directory>/WaveDAQ-Launcher/downloads/<product_id>/<version>/<file_name>`.

Device private keys and anti-clock-rollback data are stored in the operating system keychain rather than ordinary JSON files.

### 7. Add the verification module to another product

Copy the root `license_sdk/` directory into the product and set its configuration:

```python
PRODUCT_ID = "your-product-id"
SERVER_PUBLIC_KEY = "your-server-public-key"
```

Call `require_valid_license()` from the real product entry point before starting the application. The product ID must exactly match the ID registered in the administrator console. Products do not configure a version number, data directory name, or keyring service name.
