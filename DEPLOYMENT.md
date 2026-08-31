# Deploying Agent Guardrail

Goal: a live URL you can put on your resume and hand to an interviewer,
not just `localhost`. This uses Render because it deploys straight from a
Dockerfile with a generous free tier and no CLI setup, but Railway or
Fly.io work the same way if you'd rather use one of those - the
Dockerfiles are provider-agnostic.

You'll need a GitHub account with this project pushed to a repo (Render
deploys from GitHub). If it's not on GitHub yet:

```bash
cd agent-guardrail
git init
git add .
git commit -m "Agent Guardrail - Weeks 1-5"
# create a repo on github.com, then:
git remote add origin https://github.com/<you>/agent-guardrail.git
git push -u origin main
```

## 1. Database

1. Go to render.com, sign up/log in (this is the one step only you can
   do - account creation isn't something I can do on your behalf).
2. New -> PostgreSQL. Give it a name, pick the free tier, create it.
3. Once it's up, copy the "Internal Database URL" (or "External" if
   connecting from outside Render) - you'll need it in step 2.

## 2. Backend

1. New -> Web Service -> connect your GitHub repo.
2. Runtime: **Docker**. Dockerfile path: `backend/Dockerfile`. Docker
   build context: repo root (`.`) - this matters, see the comment at the
   top of `backend/Dockerfile` for why.
3. Environment variables: add `DATABASE_URL` = the connection string from
   step 1.
4. Deploy. Once live, note the public URL Render gives you
   (e.g. `https://agent-guardrail-backend.onrender.com`) - you'll need it
   in step 3. Confirm it works: visit `<that-url>/health`, should return
   `{"status":"ok"}`.

## 3. Frontend

1. New -> Web Service (or Static Site, if the provider you're using
   supports building a Vite app directly - Render's static sites can run
   a build command instead of using the Dockerfile if you prefer).
2. If using the Dockerfile route: Dockerfile path `frontend/Dockerfile`,
   build context `frontend/`, and set the build arg `VITE_API_URL` to your
   backend's public URL from step 2. (Render exposes this under "Docker
   Build Arguments" in the service's build settings - check the current
   Render docs, this UI changes.)
3. Deploy. Visit the frontend's public URL - you should see the dashboard,
   now talking to your live backend instead of localhost.

## 4. Verify it end to end

1. Open the deployed dashboard URL.
2. Run the demo agent from your own machine, pointed at the deployed
   backend instead of localhost:

   ```python
   # one-off, doesn't need to be saved anywhere
   from guardrail_sdk import Guardrail
   g = Guardrail(agent_id="finance-agent", backend_url="https://<your-backend-url>")
   ```

3. Confirm the deployed dashboard shows the activity live. If it does,
   you have a genuinely deployed, working system - not just a local demo.

## What NOT to do

- Don't commit `DATABASE_URL`, API keys, or any secret into the repo -
  they belong in the hosting provider's environment variable settings,
  never in code or `.env` files that get pushed.
- Don't point the deployed frontend at your local backend, or vice versa -
  pick one deployed pair and keep the URLs consistent.
- Free tiers on most providers spin down after inactivity and take a few
  seconds to wake up on the next request - if an interviewer clicks your
  link cold, warn them it might take a moment, or ping it yourself a
  minute before a call.
