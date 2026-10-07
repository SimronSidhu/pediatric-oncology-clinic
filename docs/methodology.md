# Methodology

One pediatric oncology clinic day, synthetic families, no charts.

SimPy advances time. Each family is a state machine. Check-in times are roughly normal, nursing and psychosocial visits are gamma, and oncology visits are log-normal. Screening adds a short normal duration. Draws happen once per seed, before the day starts.

Distress comes from a mixture. New diagnosis, symptom burden, and treatment intensity raise the chance of a moderate or high score. Caregiver stress rises with travel, symptoms, and the child's distress. High need is a high combined score.

Without a screen, detection is limited to obvious distress, a caregiver request, an existing referral, or the oncologist during the visit. With a screen, a noisy score is compared with a cutoff and the referral waits on a psychosocial resource. Families leave if the wait passes their patience.

Missed need: high latent need, no referral, no psychosocial visit. A referral that is opened but not finished the same day is counted separately. That is a capacity miss.

Monte Carlo changes the seed. Intervals are normal approximations around the sample mean. The staffing search is a small grid.

The referral model is fit on encounters from this generator, with a little label noise. The reported holdout is from that same generator. The shifted cohort lowers distress prevalence and shuffles chart distress.

Calibration, the score check, policy search, and Q-learning do not call a language model.

Calibration samples decline rate, screen completion, referral uptake, and minutes per screen. Each of 80 draws is the mean of 3 seeded days. Rejection ABC keeps the closest fifth. The targets are about 95.5% completion and about 95.5% referral of scores at 8 or higher, from an electronic caregiver screening program, and a 2-minute completion time reported for a short thermometer used with childhood cancer survivors and parents. The score distribution is not in that loss.

The score check compares the 0–10 histogram with a discretization of a published mean of 5.07 and SD of 2.78, and reports the shares at 4 (67.9%) and at 8 (16.9%). The demo mixture is richer than that, so the distance stays large.

The persona check uses 8 matched pairs. Age, score, stress, privacy, and queue are copied. Language and interpreter need are the only fields that change. The rule does not read them.

Policy search fits a Gaussian process with a Matern kernel and picks the next point by expected improvement. The grid is screening on or off, cutoff 1–9, 1–4 social workers, and 2–6 nurses (360 policies). Forty are simulated. Each utility is the mean of 2 days, and that utility is the simulator's value.

Q-learning chooses refer or watch from the distress band and the social-work queue. Each choice is updated from that family's outcome. The fixed cutoff is scored on the same held-out seeds.
