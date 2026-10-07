# Pediatric Oncology Clinic Digital Twin

A simulation of one outpatient day in a pediatric oncology clinic. Families check in, see a nurse and an oncologist, and some of them also need social work, psychology, or child life before they go home.

The demo asks what changes if every family is offered a short distress screen at check-in. More families get picked up. Check-in takes longer, and one social worker can end up with a queue. Start on universal screening (20 visits, 3 nurses, 2 oncologists, 1 social worker, 1 psychologist, 1 child life specialist, 08:00–16:00, seed 17). After that day finishes, rerun **Screening + Extra Social Worker** and compare the queue.

Press **Start**. At 1×, one simulated minute takes a quarter of a second.

This application is a research and educational simulation using synthetic data. It is not a clinical decision-support system and should not be used to guide patient care.

## How a day is produced

SimPy keeps the clock, the queues, and how long staff are busy. Each person moves through a state machine. Service times are drawn once, before the day starts, so the same seed gives the same families.

Rules decide whether a parent agrees to the screen, how much they write on the form, and whether a nurse refers. **Model decisions** can be turned on for those three choices only. The model has to return JSON that fits a fixed schema. If it doesn't, that answer is dropped and the rule is used. Monte Carlo, calibration, the policy search, and the learned referral policy stay on the rules. Calling a model once per family would be slow, and the day would not repeat.

## Analysis

These are on the Analysis page. Details and sources are in [docs/methodology.md](docs/methodology.md).

Calibration is rejection ABC: 80 draws, each one the average of 3 days. It adjusts decline rate, how often a started screen is finished, whether a high score becomes a referral, and minutes spent on the screen. The targets are 95.5% completion, 95.5% referral when the score is 8 or higher, and about 2 minutes for a short thermometer. That 2-minute number is a published completion time, not a stopwatch study of nursing.

The score check lines the simulated 0–10 histogram up against published caregiver figures: mean 5.07 (SD 2.78), 67.9% at 4 or above, 16.9% at 8 or above. The demo day has more high scores than that, on purpose, so the queue is visible. The gap is shown. The families are not quietly rewritten to close it.

The persona check is 8 pairs with the same age, score, stress, and queue. One parent needs a Punjabi interpreter. The rules do not use language. If a key is set, the model is asked both versions of each pair.

Policy search fits a Gaussian process and picks the next setup with expected improvement. Screening on or off, cutoff 1–9, 1–4 social workers, 2–6 nurses: 360 options. It runs 40 of them, two days each. The score on the page is the simulator's, not the Gaussian process prediction.

The learned policy is Q-learning over distress band and social-work queue length. It can refer or watch, and it is scored against the fixed cutoff on days it was not trained on.

The referral model is a logistic regression and a random forest, trained on synthetic encounters from this generator with a little label noise. You get a holdout from that same generator, and a second set with lower distress and the chart-distress column shuffled. The second number is there so the first one is not the only result.

## Run it

Python 3.11 or newer, and Node 20 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
uvicorn app.main:app --reload --port 8000
```

Second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The page talks to the API through the Vite proxy.

For the optional model, put `ANTHROPIC_API_KEY` in `.env` in the project root and turn on Model decisions. `ANTHROPIC_MODEL` defaults to `claude-sonnet-4-5`. `OPENAI_API_KEY` works the same way. With no key, the day still runs on the rules.

On the board, missed means high underlying need, no referral, and no psychosocial visit before discharge.

### Tests

```bash
cd backend
python -m pytest
cd ../frontend
npm test
```

A shorter contrast, without the browser:

```bash
cd backend
python ../notebooks/compare_days.py
```

## Layout

```text
backend/app/simulation     SimPy day
backend/app/agents         state machines
backend/app/services       rules and the optional model
backend/app/calibration    rejection ABC
backend/app/evaluation     score histogram and persona pairs
backend/app/surrogate      Gaussian process search
backend/app/rl             learned refer-or-watch policy
backend/app/ml             referral-risk models
backend/app/optimization   staffing grid
frontend/src               floor, controls, charts
docs/methodology.md        sources and definitions
```
