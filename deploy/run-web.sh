#!/bin/bash
# Boots the DeepSeek Harness web UI for the guardshop.shop deployment.
#
# The listener stays on 127.0.0.1: the harness ships no authentication of its
# own and its default agent preset carries the bash and filesystem tools, so
# anything that can reach this port can run commands as this user. nginx in
# front supplies TLS and the only authentication layer.
#
# --trusted-host entries satisfy the /api browser-trust fence (a DNS-rebinding
# defence, not authentication) for the authority the browser actually uses.
set -e

cd /opt/dsh/app
export HOME=/opt/dsh
export NODE_OPTIONS=--max-old-space-size=768

exec /usr/bin/node --import tsx/esm apps/cli/src/bin.ts web \
  --host 127.0.0.1 \
  --port 8099 \
  --no-open \
  --trusted-host guardshop.shop \
  --trusted-host www.guardshop.shop \
  --trusted-host guardshop.shop:9443 \
  --trusted-host www.guardshop.shop:9443
