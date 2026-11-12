# How to deploy and roll back

The app runs on Google Cloud Run, with its data in a database on the team's existing Cloud SQL instance.
Everything below uses the project `the-forge-494212`, region `us-central1`. See "Architecture" in
`docs/SYSTEM_DESIGN.md` (section 5) for how the pieces fit.

## Deploying

Merge a pull request into `main`. That is all. The **Deploy** workflow then:

1. runs the tests and lint again; **if either fails, nothing is deployed**;
2. builds the image and pushes it to Artifact Registry;
3. runs the database migrations (the `money-budget-migrate` job). **If a migration fails, nothing is deployed** and the
   database is as it was (each run is one transaction);
4. deploys the new version of the `money-budget` service.

The image is also built and started (without pushing it) on every pull request, by the "Production image" check, so a
mistake in how it is built is found before the merge and not by a failed deploy.

The address of the app is in the summary of the workflow run (`https://money-budget-<project number>.us-central1.run.app`).
Watch a deploy under the **Actions** tab, or: `gh run watch`.

## One-time setup (already done for this project)

Done by hand in Google Cloud, once. Kept here so it can be repeated or checked.

| What | Name |
|---|---|
| Database + its owner | `money_budget` on instance `the-forge-db`, user `money_budget_app` (owns only that database) |
| Secrets (Secret Manager) | `mb-db-password`, `mb-jwt-secret` |
| Service account the app runs as | `mb-run@the-forge-494212.iam.gserviceaccount.com` (Cloud SQL client; reads only the two secrets) |
| Service account GitHub uses | `mb-deploy@the-forge-494212.iam.gserviceaccount.com` (push images, deploy Cloud Run, act as `mb-run`) |
| Trust between GitHub and Google | Workload Identity pool `github`, provider `money-budget`; only `lucabattesini/money-budget` on `main` |
| Image repository | Artifact Registry `money-budget` |
| Automated backups | on, daily at 03:00, 7 kept |
| Billing alert | `Money Budget 7 CAD` (about 5 USD), emails at 50% and 100% |

GitHub **repository variables** the workflow reads (Settings > Secrets and variables > Actions > Variables; they are
names, not secrets):

| Variable | Value |
|---|---|
| `GCP_PROJECT_ID` | `the-forge-494212` |
| `GCP_REGION` | `us-central1` |
| `GCP_SQL_INSTANCE` | `the-forge-494212:us-central1:the-forge-db` |
| `GCP_RUNTIME_SA` | `mb-run@the-forge-494212.iam.gserviceaccount.com` |
| `GCP_DEPLOY_SA` | `mb-deploy@the-forge-494212.iam.gserviceaccount.com` |
| `GCP_WIF_PROVIDER` | `projects/1014661335286/locations/global/workloadIdentityPools/github/providers/money-budget` |
| `DB_USER` | `money_budget_app` |
| `DB_NAME` | `money_budget` |
| `GOOGLE_CLIENT_ID` | the Google sign-in client id (public) |

### After the first deploy (once)

1. **Make the app reachable.** A new Cloud Run service is private until told otherwise (the deploy account may not
   change who can call it):
   `gcloud run services add-iam-policy-binding money-budget --region us-central1 --member=allUsers --role=roles/run.invoker`
2. **Default categories.** The database starts empty. Create them once (safe to repeat):
   `gcloud run jobs execute money-budget-migrate --region us-central1 --args=-m,db.seed --wait`
3. **Google sign-in.** In Google Cloud Console > APIs & Services > Credentials, open the OAuth client and add the app's
   address to *Authorized JavaScript origins*.
4. **WhatsApp** is not switched on (the settings on the account page are hidden too: set the GitHub variable `WHATSAPP_ENABLED` to `true` and deploy again to show them), and until `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_ID` are set the webhook answers `503` to every message (it has no signature check yet, TKT-27, so on a public address it must not accept messages from anyone). When it is, add its secrets, give `mb-run` access to them and set
   `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` and `WHATSAPP_VERIFY_TOKEN` on the service, then point Meta's webhook at
   `<address>/webhook/`.

## Rolling back

Cloud Run keeps every earlier version (revision). To send all traffic back to the previous one:

```bash
gcloud run revisions list --service money-budget --region us-central1
gcloud run services update-traffic money-budget --region us-central1 --to-revisions=<REVISION>=100
```

This takes seconds. **Migrations are not rolled back**, so the previous version has to run on the newer database.
Therefore write migrations that the previous release can live with (add columns as optional first; remove things in a
later release). A migration that cannot be survived that way (like the move to UUIDs) means restoring the database
from a backup instead: see below.

To go forward again, merge a fix or run `gcloud run services update-traffic money-budget --region us-central1 --to-latest`.

## Backups and restoring

Backups are automatic and belong to the whole shared instance (daily, 7 kept). **Never restore over the shared
instance**: that would overwrite the other apps' data too. To check a backup or recover from a mistake, restore it into a
scratch instance and copy what is needed:

```bash
gcloud sql backups list --instance the-forge-db
gcloud sql instances clone the-forge-db scratch-restore --point-in-time <TIMESTAMP>   # or restore a backup into a new instance
# look at the money_budget database there, dump what is needed, then:
gcloud sql instances delete scratch-restore
```

## Good to know

- The Claude connector (`/mcp`, TKT-72) is served by the same service, so it needs nothing more. Phones reach it at
  `https://<the service address>/mcp`. If the sign-in pages show a wrong address (for example `http://`), set `PUBLIC_URL`. Setting it is advisable in production.
  Its rate limit is counted per instance.

- The service is capped at 2 instances and the pool at 2 connections each, so it cannot use up the shared database's
  connections (the other apps' limit is the same instance). The migration job uses 1.
- Imports and exports run after the response is sent, so the service keeps its CPU allocated (`--no-cpu-throttling`).
  With no traffic the service scales to zero, so the first visit after a quiet period takes a second or two.
- Passwords and keys live only in Secret Manager. The image holds none (`.dockerignore` keeps `.env` out), and GitHub
  holds no key file.
- If the migration step fails with a permissions error on the first run, the deploy account is missing a role:
  the error names it. Grant it and re-run the workflow.
