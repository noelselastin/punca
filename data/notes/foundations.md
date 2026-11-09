# Foundations (curated demo notes)

> Written for the Punca prototype as stand-in course notes. Replace with real APU module notes (with permission) before any real use.

## fractions-ratios | Fractions and ratios
To add or subtract fractions, rewrite them over a common denominator first: 2/3 + 1/4 = 8/12 + 3/12 = 11/12. Never add the denominators. To multiply, multiply tops and bottoms; to divide, multiply by the reciprocal. A ratio a:b compares two quantities and is simplified like a fraction, by dividing both parts by their greatest common factor: 30:45 = 2:3. Keep the order the question asks for.

## exponents | Exponents and powers
For the same base: a^m · a^n = a^(m+n), a^m / a^n = a^(m-n) and (a^m)^n = a^(mn). Any non-zero number to the power 0 is 1. A negative exponent means a reciprocal, not a negative number: 2^(-3) = 1/2^3 = 1/8. The number e ≈ 2.718 is the base of the natural exponential e^x, which appears in sigmoid, softmax and many ML formulas.

## algebra | Rearranging equations
Whatever you do to one side of an equation, do to the other. Undo operations in reverse order: for 3x + 5 = 20, first subtract 5 (3x = 15), then divide by 3 (x = 5). To make x the subject of y = (x - b)/a, multiply both sides by a to get ay = x - b, then add b: x = ay + b. Watch the signs when a term moves across.

## logarithms | Logarithms
A logarithm answers "which power?": log_b(y) = x means b^x = y, so log2(32) = 5 because 2^5 = 32. The natural log ln uses base e, and ln(e^k) = k. Log rules: ln(ab) = ln a + ln b, ln(a/b) = ln a - ln b, ln(a^k) = k ln a. There is no rule for ln(a + b). Logs turn products into sums, which is why log-likelihoods and cross-entropy use them.

## functions | Functions
A function assigns exactly one output to each input; f(x) = 2x^2 - 1 means "square x, double it, subtract 1", so f(3) = 2·9 - 1 = 17. Respect the order of operations: the power applies before the coefficient. Different inputs may share an output (y = x^2 is a function), but one input may not have two outputs, so x = y^2 does not define y as a function of x.

## function-composition | Function composition
f(g(x)) means: apply the inner function g first, then the outer function f to its result. With f(x) = x^2 and g(x) = x + 3, f(g(x)) = (x + 3)^2, while g(f(x)) = x^2 + 3, so order matters. To evaluate g(f(4)), work from the inside out. Spotting the inner function (for sin(5x) it is 5x) is the first step of the chain rule.

## linear-functions | Linear functions and slope
A straight line is y = mx + c. The slope m is rise over run between two points: through (1, 2) and (3, 8), m = (8 - 2)/(3 - 1) = 3. The y-intercept c is the value of y when x = 0. A slope tells you how much y changes when x increases by 1; this is the idea the derivative generalises to curves.

## summation | Summation notation
Σ_{i=1}^{n} a_i means a_1 + a_2 + ... + a_n. Σ_{i=1}^{4} i = 1 + 2 + 3 + 4 = 10. Constants factor out: Σ c·x_i = c · Σ x_i, so with x = (1, 4, 2), Σ 2x_i = 2 · 7 = 14. Means, dot products, expected values and loss functions are all written with Σ.
