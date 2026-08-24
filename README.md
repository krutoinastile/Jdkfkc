# Jdkfkc

Infrastructure for the `guardshop.shop` deployment of
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness).

See [`deploy/README.md`](deploy/README.md) for the live URL, the reason TLS runs
on 9443 instead of 443, why the settings/credentials UI is reachable only over an
SSH tunnel, and the security caveats of exposing an agent harness that ships
`bash` and filesystem tools.

```sh
sudo DOMAIN=guardshop.shop ./deploy/install.sh
```
