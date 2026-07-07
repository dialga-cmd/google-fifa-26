# FanWayfinder

FanWayfinder is an AI-powered stadium navigation assistant designed for the FIFA World Cup 2026 experience. It helps fans find facilities, navigate to sections, receive accessibility-aware guidance, and interact through voice or text.

## What the project does

- Provides stadium navigation assistance for fans and event staff
- Supports multilingual and voice-enabled interaction
- Uses a lightweight knowledge base and routing graph for wayfinding
- Includes a simple accessibility-conscious frontend experience
- Offers a backend API that can be tested locally or deployed to a cloud platform

## Current capabilities

- Natural-language queries such as “Where is the nearest restroom?”
- Route suggestions based on a stadium graph
- Congestion-aware routing concept using live-style edge updates
- Voice and text input/output support in the frontend
- Accessibility-friendly interface elements and ARIA labels
- Token-based authentication flow for API requests

## Local setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd fan_wayfinder
```

### 2. Create and activate a Python environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate sample data

```bash
python3 src/generate_graph.py
```

### 5. Run the backend

```bash
python3 src/api.py
```

The API will be available at:
- http://localhost:8000/docs
- http://localhost:8000/advice

### 6. Open the frontend

Open the file [frontend/index.html](frontend/index.html) in a browser, or serve the folder with a simple static server if preferred.

## Run tests

```bash
python3 -m pytest tests/test_basic.py tests/test_api_comprehensive.py tests/test_new_features.py -v
```

## Project structure

```text
fan_wayfinder/
├── src/
│   ├── api.py
│   ├── generate_graph.py
│   └── sensor_mock.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/
│   ├── kb_chunks.json
│   ├── stadium_graph.gexf
│   └── stadium_graph.json
├── tests/
├── api/
│   └── advice.py
├── requirements.txt
├── pyproject.toml
└── vercel.json
```

## Deploying to Vercel

Vercel can host a lightweight serverless API for this project.

### Optional AI configuration

If you want the app to use a real AI provider for richer responses, set one of these environment variables in your deployment settings:

```bash
export GEMINI_API_KEY="your-gemini-key"
export GROQ_API_KEY="your-groq-key"
export AI_PROVIDER="auto"
```

The app will use Gemini first when available, then Groq, and otherwise fall back to the built-in local logic.

### Prerequisites

- A Vercel account
- The Vercel CLI installed locally

```bash
npm install -g vercel
```

### Deploy

```bash
vercel
```

Follow the prompts to link the project and deploy it.

### Notes

- The Vercel entrypoint uses [api/advice.py](api/advice.py).
- The frontend is still a static file and can be served from Vercel as well if you add a static hosting setup later.
- For production, set environment variables such as a secret key and any future AI provider credentials.

## Submission checklist

- Ensure the repo is public or shared with the judges
- Include a short demo video or demo link
- Confirm the backend runs locally and on your deployment target
- Prepare a concise pitch explaining the problem, solution, and impact
- Include accessibility and multilingual value in your presentation

## License

MIT License.