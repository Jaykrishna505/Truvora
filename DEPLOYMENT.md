# VS Code -> GitHub -> AWS Lightsail

Deployment version: v0.1.18 (prepared; tag after the first successful deployment).

Edit and test on your Windows computer. Push to `All_local_businesses_branch`.
GitHub Actions tests the application and deploys that exact commit over SSH.
Pull requests run tests only. No AWS access keys or server access to GitHub are needed.

The application stays bound to `127.0.0.1:8000`. Your existing SSH tunnel still
works. This setup does not expose the app publicly or complete live billing.

## 1. Put these files in the GitHub repository

Open the actual Truvora Git checkout in VS Code, at the folder containing
`requirements.txt` and `app/main.py`. If you use a different checkout from this
workspace, copy `.github`, `.gitattributes`, `deploy`, `tests`, and this guide
into its root. The workflow must be at `.github/workflows/deploy.yml` in the
GitHub repository root, not under `outputs/`.

Check your branch and remote in the VS Code terminal:

```powershell
git status
git remote -v
git branch --show-current
```

Use the existing checkout of `All_local_businesses_branch`. Do not switch
branches with uncommitted work you need to preserve. If no remote exists,
configure it once:

```powershell
git remote add origin https://github.com/Jaykrishna505/Truvora.git
```

Do not force-push or replace the remote branch with unrelated local history.
When needed, clone the GitHub branch into another folder and copy the new files
there. Ensure neither `.env` nor `data/app.db` is tracked. An empty `data/`
directory does not need to be committed; the app creates it.

```powershell
git ls-files .env data
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git add .github .gitattributes deploy tests DEPLOYMENT.md
git commit -m "Add automated Lightsail deployment"
git push origin All_local_businesses_branch
```

The first deployment job will fail until the next two sections are complete.
Tests should pass. Re-run the deployment after setup.

## 2. One-time server setup (Lightsail browser SSH)

Stop the manually running Uvicorn process with Ctrl+C in its original terminal.
This is required to free port 8000. Your first setup briefly interrupts access.
Then run these commands in the Ubuntu terminal:

```bash
cd ~/truvora
git pull --ff-only origin All_local_businesses_branch
bash -n deploy/bootstrap.sh deploy/deploy.sh deploy/rollback.sh
bash deploy/bootstrap.sh
sudo systemctl status truvora --no-pager
```

If Git reports changes or diverged history, resolve those before continuing;
do not use a hard reset. Check the page itself with:

```bash
curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8000/
```

The bootstrap copies the existing server `.env` and uses SQLite's backup API
to copy the existing database on its first run. It does not overwrite an
existing shared configuration or database. The service starts automatically
after reboot; you can close the Lightsail browser terminal afterward.

Runtime layout:

```text
/home/ubuntu/truvora-runtime/
  current -> releases/<timestamp>-<commit>-<process>
  releases/              # code and a virtual environment per release
  shared/.env            # server secrets; never uploaded by Actions
  shared/data/app.db     # database shared across releases
  backups/               # SQLite snapshot before each deployment
  incoming/              # Git archives uploaded by Actions
```

Later configuration changes belong in `~/truvora-runtime/shared/.env`.
Editing `~/truvora/.env` no longer changes the running release.

## 3. Give GitHub its own deployment key

Use a dedicated key rather than uploading your Lightsail default private key.
Run on your Windows computer in PowerShell:

```powershell
ssh-keygen -t ed25519 -C "truvora-github-deploy" -f "$env:USERPROFILE\.ssh\truvora-github-deploy"
```

Use an empty passphrase for this automation key. Open the `.pub` file locally
and copy its single public-key line. In the Lightsail browser SSH terminal:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
```

Keep all existing lines. Append the new public key on its own line, prefixed
with `restrict `, for example:

```text
restrict ssh-ed25519 AAAA... truvora-github-deploy
```

```bash
chmod 600 ~/.ssh/authorized_keys
```

`restrict` disables forwarding and interactive terminals for this key, while
allowing deployment commands. This key can execute commands as ubuntu; keep
it private and restrict who can push to the deployment branch. On the standard
Lightsail Ubuntu image, ubuntu has passwordless sudo. The scripts use that to
restart only `truvora`, but the account itself has broader permissions.

In GitHub, open the repository -> Settings -> Secrets and variables -> Actions
-> New repository secret. Add:

| Secret | Value |
|---|---|
| `LIGHTSAIL_HOST` | Static public IPv4, currently `3.130.61.167`; verify in Lightsail |
| `LIGHTSAIL_SSH_KEY` | Complete contents of the NEW private key, including header/footer |
| `LIGHTSAIL_KNOWN_HOSTS` | Verified ED25519 host-key line described below |

Do not paste private keys into chat or commit them. To obtain the host-key line,
run this inside the trusted Lightsail browser SSH terminal:

```bash
awk '{print "3.130.61.167", $1, $2}' /etc/ssh/ssh_host_ed25519_key.pub
```

Use the actual static IP if it differs. This line contains a public host key.
The workflow requires host-key verification; it does not blindly trust a
fresh `ssh-keyscan` result.

GitHub-hosted runners must be able to reach port 22. If the Lightsail SSH
firewall allows only your home IP, these runners cannot connect. Allowing
TCP 22 from Anywhere enables the simple workflow, with key authentication;
keep the browser SSH rule as needed. Do not open port 8000. A fixed-IP runner
is an alternative later if you want to restrict SSH source addresses.

Open GitHub -> Actions -> Test and deploy to Lightsail -> re-run the failed
deployment, or use Run workflow on `All_local_businesses_branch`.

## 4. Normal changes from VS Code

```powershell
git switch All_local_businesses_branch
git pull --ff-only
```

Edit and test your change locally. Then:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git status
git add app tests
git commit -m "Describe the change"
git push origin All_local_businesses_branch
```

Stage other intended files explicitly when needed. Check Actions for the green
test and deployment jobs before considering the update live. Each deployment
has brief downtime while the single worker restarts. Secrets and client data
are preserved. No additional SSH tunnel is needed for deployment.

GitHub Actions usage depends on repository visibility and your account's
included minutes; check usage before enabling paid overages. The workflow
does not create additional AWS servers.

## Logs, versioning, and rollback

In Lightsail browser SSH:

```bash
sudo journalctl -u truvora -n 80 --no-pager
cat ~/truvora-runtime/current/DEPLOYED_COMMIT
ls ~/truvora-runtime/releases
df -h
```

After a successful milestone, tag the exact deployed commit locally:

```powershell
git tag v0.1.18 COMMIT_SHA
git push origin v0.1.18
```

Usually use `git revert COMMIT_SHA` and push a new corrective commit. For an
urgent code rollback on the server, select a directory shown by `ls`:

```bash
bash ~/truvora-runtime/current/deploy/rollback.sh RELEASE_DIRECTORY_NAME
```

Code rollback does not rewind customer data. Schema changes need a migration
and recovery plan: an old release may not work with a newer schema. Backups
are created before deployment, but never restored automatically. Server-local
backups do not protect against losing the whole instance; add off-server
backups before client onboarding. Check disk space and remove obsolete
releases, uploaded archives, and backups intentionally as they accumulate.

HTTPS, a public hostname, messaging limits, production secrets, and the known
payment/reset security fixes are separate remaining launch tasks. This workflow
automates deployment; it does not resolve those application issues.
