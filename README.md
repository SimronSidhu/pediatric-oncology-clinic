# Pediatric Oncology Clinic Digital Twin

One simulated outpatient day in a pediatric oncology clinic. Families check in, see a nurse and an oncologist, and some need social work, psychology, or child life before they leave.

The question is operational. If every family is offered a distress screen at check-in, who gets found, and what happens to the queue?

The demo day is universal screening: 20 visits, 3 nurses, 2 oncologists, 1 social worker, 1 psychologist, 1 child life specialist, 08:00–16:00, seed 17. Press **Start**, watch the social-work queue, then rerun **Screening + Extra Social Worker**.

This application is a research and educational simulation using synthetic data. It is not a clinical decision-support system and should not be used to guide patient care.

## How the day runs

SimPy advances the clock and holds the queues and staff time. Each person is a state machine. Service times are drawn once from a seeded generator, so the same seed replays the same families.

Three judgments are separate from the clock: whether a parent agrees to the screen, how much they put on the form, and whether a nurse refers. Those use rules unless **Model decisions** is turned on. The model has to return JSON that matches a schema. Bad output is dropped and the rules are used. Monte Carlo, calibration, policy search, and the learned referral policy always use the rules.

## Analysis page

- Calibration. Rejection ABC, 80 prior draws, 3 days each. Targets: 95.5% completion, 95.5% referral when the score is 8 or higher, and a 2-minute thermometer time.
- Scores. Full 0–10 histogram, plus the share at 4 and at 8, set next to published caregiver figures. The demo day is enriched, so the right tail runs high.
- Personas. 8 pairs. Same age, score, stress, and queue. One parent needs a Punjabi interpreter. The rules do not use language.
- Policy search. Gaussian process, expected improvement, 360 candidate policies, 40 simulated. Each score is the mean of 2 days.
- Learned referrals. Q-learning on distress band and social-work queue, scored against the fixed cutoff on held-out seeds.
- Referral model. Logistic regression and a random forest. One holdout comes from the training generator. A second cohort has lower distress and shuffled chart distress.

## Run it

Python 3.11 or newer, Node 20 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies the API.

For model decisions, put `ANTHROPIC_API_KEY` in `.env` at the project root. `ANTHROPIC_MODEL` defaults to `claude-sonnet-4-5`. `OPENAI_API_KEY` works the same way. Leave both unset and the day uses the rules.

### Tests

```bash
cd backend
python -m pytest
cd ../frontend
npm test
```

### Command-line contrast

```bash
cd backend
python ../notebooks/compare_days.py
```

At 1×, one simulated minute takes a quarter of a second. Missed need means high latent need and no referral or psychosocial visit before discharge.

## Layout

```text
backend/app
  api/                HTTP and websocket
  agents/             state machines
  simulation/         SimPy clinic day
  synthetic_data/     correlated fictional families
  services/           stress and decisions
  analytics/          metrics, bottlenecks, Monte Carlo
  calibration/        rejection ABC
  evaluation/         score distribution and persona pairs
  surrogate/          Gaussian process search
  rl/                 learned referral policy
  ml/                 referral-risk models
  optimization/       staffing grid search
frontend/src          floor, experiments, charts
tests/                pytest
notebooks/            command-line contrast
docs/                 methodology
```
