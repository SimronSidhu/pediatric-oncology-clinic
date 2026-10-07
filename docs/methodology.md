# Methodology

Synthetic families only. No charts, and no claim that this is a twin of a real clinic.

## The day

SimPy moves the clock. Arrivals, rooms, and staff are resources with queues. Check-in times are roughly normal. Nursing and psychosocial visits are gamma. Oncology visits are log-normal. A screen adds a short normal duration on top of check-in. All of those draws happen once, from the seed, before anyone arrives. Replaying the seed does not draw them again.

Distress is a mixture. A new diagnosis, a higher symptom burden, and more intensive treatment raise the chance of a moderate or high score. Caregiver stress goes up with travel, symptoms, and the child's distress. High need is that combined score, not the number written on the form.

If screening is off, a family is noticed only in a few cases: the distress is obvious, the caregiver asks, there is already a referral, or the oncologist picks it up during the visit. Those paths miss a lot. If screening is on, the recorded score is the latent distress plus noise, then reduced if the parent only partly fills in the form. A score at or above the cutoff opens a referral, and that referral waits for social work, psychology, or child life. If the wait runs past the family's patience, they leave.

"Missed" is high need with no referral and no psychosocial visit. A referral that was opened but not finished the same day is counted on its own. That second count is a capacity problem, not a failure to notice the family.

## Calibration

Four parameters are sampled from wide ranges: decline rate, chance a started screen is completed, chance a qualifying score is actually referred, and mean minutes on the screen. Each of 80 draws is run as 3 seeded days and then averaged. Rejection ABC keeps the closest fifth of those draws and reports the median.

The distance uses three published figures. An electronic caregiver screen in pediatric oncology reached 1,923 of 2,013 patients (95.5%), and 471 of 493 scores at 8 or higher were referred to social work (95.5%). A short thermometer used with childhood cancer survivors and their parents is described as taking less than 2 minutes to complete, so the time target is 2 minutes. That is a completion-time claim. It is not a time-and-motion study of staff.

How often scores land at 8 or higher is not in this loss. Changing decline rate or minutes per screen cannot fix the mix of families, and the demo mix is heavier than the published one so that a queue shows up.

A separate multi-site Psychosocial Assessment Tool trial screened 73% of eligible families (529/721). That number is program reach across sites. It is not the check-in completion rate above, so it is reported beside the fit and left out of the distance.

## Scores

Completed screens are binned from 0 to 10. The reference bins are a normal distribution with mean 5.07 and SD 2.78, cut into those same integers. Those two numbers, and 67.9% scoring 4 or higher, come from the Distress Thermometer for Parents in parents of children with cancer. The 16.9% at 8 or higher is the electronic screening program above (325 of 1,923 caregivers, ever, across visits — not a single morning).

The check reports the mean, the SD, both of those shares, total variation between the histograms, and a Kolmogorov–Smirnov distance on the cumulative shares. On the demo day the right tail is higher than 16.9%. That gap is the result. It is not tuned away.

## Personas

Eight pairs. Within a pair, age, score, stress, privacy, and queue length are copied. The only change is language, and whether a Punjabi interpreter is needed. The prompt does not add a description of the parent beyond those fields.

The rule for declining and for how much is disclosed does not read language. If the two rule answers in a pair differ, something is wrong in the rule. If a model key is set, the same three questions (agree to screen, how much to disclose, nurse referral) are asked on both sides. A difference there belongs to that procedure. It is not evidence about real families.

## Policy search

The options are screening on or off, a referral cutoff from 1 to 9, 1 to 4 social workers, and 2 to 6 nurses (360 combinations). A Gaussian process with a Matern kernel is fit to the runs so far. Expected improvement chooses the next combination that has not been run. Forty combinations are simulated. Each one is the mean utility of 2 days with 20 families.

Utility is the share of families with need who were seen, minus a penalty for misses, mean psychosocial wait, and extra nurses or social workers. The page reports the simulator's utility at the chosen point.

## Learned referrals

Q-learning. The state is the score band (0–2, 3–5, 6–8, 9–10) and whether the social-work queue is empty, has 1–2 waiting, or has 3 or more. The action is refer or watch. Training is 48 days. Each decision is updated from that family's outcome at the end of the day, not from one score shared by the whole clinic. The comparison with the fixed cutoff uses 8 seeds that were not in training.

## Referral model

Logistic regression and a random forest. Features are things that would be known before today's screen: age, visit type, symptoms, chart distress, caregiver stress, travel, treatment intensity, language support, prior psychosocial contact, and a previous wait. Labels are high need from the generator, flipped at random about 4% of the time.

The first metrics are a 25% holdout from that same generator. The second set is built with a lower distress prevalence, and then the chart-distress column is shuffled so it no longer tracks the label. Both numbers are shown. Neither one is an external clinical validation.
