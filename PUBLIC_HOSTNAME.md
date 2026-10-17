# Free hostname and HTTPS (v0.1.19, prepared)

Proposed address: https://truvora.3-130-61-167.sslip.io

Confirm that 3.130.61.167 is the attached Lightsail static IP before using it.
sslip.io resolves names containing that IP without domain registration. The
hostname is public and depends on a third-party shared DNS service; certificate
issuance can hit shared rate limits. Do not buy a second server.

## Prepare in VS Code

Copy `deploy/truvora.nginx.conf` into the Git-connected Truvora checkout.
Commit and push this file, then wait for a green deployment. The deployment
workflow does not change Nginx automatically, so future pushes will not overwrite
the certificate directives Certbot adds on the server.

## First checks (Lightsail browser SSH)

```bash
sudo systemctl is-active truvora
getent ahostsv4 truvora.3-130-61-167.sslip.io
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

The first command must report active and DNS must resolve to the static IP.
In the Lightsail Networking tab, allow inbound TCP 80 and 443 from Anywhere.
Keep TCP 8000 private. Check `sudo ufw status` too; if UFW is active, allow
`Nginx Full` before certificate validation.

## Public activation

Before activation, complete the known public-access fixes: disable uncharged
payment activation, require signed payment webhooks, stop exposing password-reset
links when mail is unconfigured, and configure secure cookies for HTTPS. Limit
messaging before accepting untrusted trial accounts. Publishing this hostname
does not implement those changes.

Only after those fixes, run:

```bash
sudo install -m 644 ~/truvora-runtime/current/deploy/truvora.nginx.conf /etc/nginx/sites-available/truvora
sudo ln -s /etc/nginx/sites-available/truvora /etc/nginx/sites-enabled/truvora
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d truvora.3-130-61-167.sslip.io --redirect
```

If the symlink already exists, leave it in place; do not recreate or overwrite
an existing certificate-enabled configuration. Stop if nginx validation fails.
Certbot asks for a certificate contact email and agreement to its terms.
If issuance is rate-limited, retain private access and inspect the error rather
than repeatedly requesting certificates or publishing login over plain HTTP.

Edit only APP_URL in the shared server configuration, preserving its other values:

```bash
nano ~/truvora-runtime/shared/.env
```

Set `APP_URL=https://truvora.3-130-61-167.sslip.io`, then:

```bash
sudo systemctl restart truvora
curl -I https://truvora.3-130-61-167.sslip.io/
sudo certbot renew --dry-run
systemctl list-timers --all | grep certbot
```

A HEAD request may return 405; use a browser GET to verify the login page.
Test from a phone on mobile data without the SSH tunnel. New feedback links
must use the HTTPS hostname. Previously sent localhost links do not change.
Stripe test webhook endpoints, if configured, must also use the new address.

The browser SSH window and Windows tunnel can close after public access is
confirmed. Keep development in the local Git checkout and deploy by pushing.
Buying a domain later only requires updating DNS, the Nginx server name,
certificate, APP_URL, and provider callback URLs. Keep the temporary hostname
working while previously sent feedback links still rely on it.
