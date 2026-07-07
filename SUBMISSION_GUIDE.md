# FanWayfinder Submission Guide

## 1. Final local check

Run the tests:

```bash
python3 -m pytest tests/test_basic.py tests/test_api_comprehensive.py tests/test_new_features.py -v
```

## 2. Prepare the repo

Make sure your repository is pushed to GitHub with the latest changes.

```bash
git status
git add .
git commit -m "Polish FanWayfinder for hackathon submission"
git push
```

## 3. Deploy to Vercel

Install the CLI:

```bash
npm install -g vercel
```

Deploy:

```bash
vercel
```

When prompted, choose the current folder and confirm the deployment.

## 4. Share your demo assets

Prepare:
- A public GitHub repo link
- A deployed Vercel link
- A short demo video or screen recording
- A short pitch describing the problem and your solution

## 5. Submission checklist

- App runs locally
- API endpoint responds
- Tests pass
- README is clear
- Demo link works
- Presentation is ready
