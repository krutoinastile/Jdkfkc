# DeepSeek Harness on guardshop.shop

Deployment of [`deepseek-ai/deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness)
(MIT) on the Ubuntu 24.04 host serving `guardshop.shop`.

**Live URL: `https://guardshop.shop:9443/`** (HTTP Basic Auth; port 80 redirects there)

## Layout

| Piece | Value |
| --- | --- |
| Checkout | `/opt/dsh/app` |
| Service | `dsh-web.service`, runs as `dsh` |
| App listener | `127.0.0.1:8099` (loopback only) |
| Public TLS | `9443` via nginx |
| Certificate | Let's Encrypt, `guardshop.shop` + `www.guardshop.shop`, auto-renewing |
| Logs | `/var/log/dsh-web.log`, `/var/log/nginx/{access,error}.log` |

## Why port 9443 and not 443

The host already runs a **Remnawave VPN node** (`rw-node`, Docker with
`network_mode: host`) bound to `*:443`, plus `rw-core` on 8443 and 1234.
Binding nginx to 443 would have dropped every existing VPN client, so TLS
terminates on 9443 instead. Port 80 was free and is used for the ACME HTTP-01
challenge plus a redirect.

To move the app onto a clean `https://guardshop.shop` you must first free 443,
which means one of:

- Repoint the Remnawave node to another port in its panel and re-issue client
  configs (breaks existing clients until they update).
- Configure the node's Xray inbound with a fallback to `127.0.0.1:8099`, so a
  single 443 listener serves both proxy traffic and the site. The node's Xray
  config is pushed from the Remnawave panel, so this is a panel-side change and
  cannot be done from the node alone.

## The configuration plane is loopback-only — by design

The settings and credentials UI **will not work over the public URL**. Calls
return `403 forbidden`. This is intentional upstream behaviour, not a
misconfiguration: `packages/client/connection/src/index.ts` pins a
`PRIVILEGED_METHODS` set to loopback even on a trusted-host deployment —

> `trustedHosts` is a DNS-rebinding fence, explicitly not authentication, so the
> whole configuration plane stays loopback-same-origin until a real
> authentication layer exists.

Pinned methods include `settings.*`, `credentials.describe/set/unset`,
`llm.discoverModels`, `agentPreset.read/copy/remove/openDocument`, and
`host.pickDirectory/openPath`.

So to add your model API key or change settings, reach the app over loopback
with an SSH tunnel from your own machine:

```sh
ssh -N -L 8099:127.0.0.1:8099 root@78.17.124.240
```

Then open <http://127.0.0.1:8099/> locally. The trust fence accepts the loopback
authority, so the settings and credentials screens work there. `--trusted-host`
cannot lift this restriction.

## Security posture

Read this before widening access.

The harness's default agent preset carries the `bash` and filesystem tools. The
upstream source is blunt about what that means:

> the deployment's own default already carries `bash` and the filesystem tools,
> so any caller that may start a session at all can already run commands as this
> process.

**Anyone who gets past basic auth can execute commands as the `dsh` user.** The
mitigations in place:

- The app listens on `127.0.0.1` only and is never directly exposed.
- nginx basic auth is the sole authentication layer — the app has none.
- It runs as the unprivileged `dsh` user, not root, with `NoNewPrivileges=yes`.

Worth tightening further: restrict 9443 to known source IPs, put a real identity
provider in front, or keep it loopback-only over the SSH tunnel and not publish
it at all. Also note `ufw` is inactive on this host and the harness is a
developer preview with a release-candidate CLI.

## Operations

```sh
systemctl status dsh-web              # service state
journalctl -u dsh-web -f              # supervisor log
tail -f /var/log/dsh-web.log          # app output
systemctl restart dsh-web             # restart
nginx -t && systemctl reload nginx    # validate + apply proxy changes
certbot renew --dry-run               # test renewal
```

Rotate the basic-auth password:

```sh
htpasswd -c /etc/nginx/.htpasswd-dsh admin && systemctl reload nginx
```

Update the checkout:

```sh
sudo -u dsh git -C /opt/dsh/app pull
sudo -u dsh env HOME=/opt/dsh NODE_OPTIONS=--max-old-space-size=3072 \
  bash -c 'cd /opt/dsh/app && pnpm install && pnpm run build'
systemctl restart dsh-web
```

## Host notes

The box is 1 vCPU / 1.9 GB RAM / 15 GB disk. The build peaks near 2 GB of
anonymous memory across ~246 workspace projects, so swap was raised from 512 MB
to 4 GB to keep `tsc` from being OOM-killed. That leaves roughly 3.2 GB of disk
free — thin, so watch disk before pulling large updates. `NODE_OPTIONS` caps the
runtime heap at 768 MB and systemd sets `MemoryHigh=900M` so the app cannot
starve the VPN node.

## Reproducing

```sh
sudo DOMAIN=guardshop.shop ./deploy/install.sh
```

Idempotent and safe to re-run. It refuses to start if a non-nginx process holds
80 or 9443, and prints a freshly generated basic-auth password on first run.
