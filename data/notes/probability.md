# Probability and statistics (curated demo notes)

> Written for the Punca prototype as stand-in course notes. Replace with real APU module notes (with permission) before any real use.

## probability | Basic probability
For equally likely outcomes, P(event) = favourable outcomes / total outcomes: a fair die is even with probability 3/6 = 1/2. Probabilities lie between 0 and 1, and P(not A) = 1 - P(A). For independent events, multiply: P(two heads) = 1/2 · 1/2 = 1/4. Adding probabilities is only valid for events that cannot happen together.

## conditional-probability | Conditional probability
P(A | B), "the probability of A given B", restricts attention to the cases where B happened: P(A | B) = P(A and B) / P(B). If P(A and B) = 0.12 and P(B) = 0.4, then P(A | B) = 0.3. Divide, do not multiply. In general P(A | B) ≠ P(B | A): the share of ML students who take Stats differs from the share of Stats students who take ML.

## bayes-theorem | Bayes' theorem
Bayes' theorem reverses a conditional: P(A | B) = P(B | A) · P(A) / P(B). P(A) is the prior (belief before evidence), P(B | A) the likelihood, P(B) the evidence and P(A | B) the posterior. Example: with P(B | A) = 0.9, P(A) = 0.1 and P(B) = 0.2, P(A | B) = 0.09 / 0.2 = 0.45. A high likelihood does not mean a high posterior if the prior is small.

## expected-value | Random variables and expected value
A random variable X gives a number for each outcome. Its expected value is the probability-weighted average E[X] = Σ x · P(X = x). If X = 1 with probability 0.2 and 5 with probability 0.8, E[X] = 0.2 + 4 = 4.2. For a fair die E[X] = 3.5, which is not itself a possible roll. Expected loss over the data is what training minimises.

## mean-variance | Mean, variance and standard deviation
The mean is the sum divided by the count: (2 + 4 + 9)/3 = 5. Population variance is the mean of the squared deviations from the mean: for 1 and 3 the mean is 2, the squared deviations are 1 and 1, so the variance is 1. The sample variance divides by n - 1 instead. Standard deviation is the square root of the variance, in the original units.
