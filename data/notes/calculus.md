# Calculus (curated demo notes)

> Written for the Punca prototype as stand-in course notes. Replace with real APU module notes (with permission) before any real use.

## limits | Limits
lim_{x→a} f(x) is the value f(x) gets close to as x gets close to a. It can exist even where f(a) is undefined: (x^2 - 1)/(x - 1) is undefined at x = 1, but it equals x + 1 everywhere else, so the limit as x → 1 is 2. As x → ∞, 1/x → 0. The derivative is defined as a limit of slopes.

## derivatives | Derivatives
The derivative f'(a) is the instantaneous rate of change of f at a: the slope of the tangent line, defined as the limit of (f(a + h) - f(a))/h as h → 0. f'(a) = 0 means a horizontal tangent (a flat point, often a minimum or maximum). If s(t) is position, s'(t) is velocity. In ML, the derivative of the loss tells you which way to nudge a weight.

## derivative-rules | Basic differentiation rules
Power rule: d/dx x^n = n·x^(n-1), so d/dx 4x^3 = 12x^2 and d/dx x^(-1) = -x^(-2). Constants vanish: d/dx 7 = 0. Constant multiples stay: d/dx (c·f) = c·f'. Sums split: d/dx (x^2 + 7x - 3) = 2x + 7. Bring the power down and reduce it by one; do not keep the old power.

## chain-rule | Chain rule
For a composite function y = f(g(x)), dy/dx = f'(g(x)) · g'(x): differentiate the outer function (leaving the inside alone), then multiply by the derivative of the inside. Example: d/dx (3x + 1)^2 = 2(3x + 1) · 3 = 6(3x + 1). The most common mistake is forgetting the inner derivative. d/dx e^(2x) = 2e^(2x) and d/dx sin(x^2) = 2x·cos(x^2). Backpropagation is the chain rule applied through every layer of a network.

## exp-log-derivatives | Derivatives of exp and log
d/dx e^x = e^x, the only function that is its own derivative, and d/dx (3e^x) = 3e^x. d/dx ln(x) = 1/x for x > 0. Do not use the power rule on e^x: the variable is in the exponent, not the base. Combined with the chain rule: d/dx ln(g(x)) = g'(x)/g(x), which is how cross-entropy gradients are derived.

## partial-derivatives | Partial derivatives
For a function of several variables, the partial derivative ∂f/∂x differentiates with respect to x while treating every other variable as a constant. For f(x, y) = x^2·y + 3y: ∂f/∂x = 2xy (3y has no x, so it vanishes) and ∂f/∂y = x^2 + 3. A model's loss depends on many weights, so we need one partial derivative per weight.

## gradient-vector | Gradient
The gradient ∇f collects all partial derivatives into a vector: for f(x, y) = x^2 + 3y, ∇f = (2x, 3). It points in the direction of steepest increase of f, and its length is how steep that increase is. Where ∇f = (0, 0) the function is flat: a minimum, maximum or saddle point. Gradient descent moves against the gradient.
