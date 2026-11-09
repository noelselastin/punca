# Machine learning (curated demo notes)

> Written for the Punca prototype as stand-in course notes. Replace with real APU module notes (with permission) before any real use.

## loss-functions | Loss functions
A loss function scores how wrong predictions are; training minimises it. Mean squared error averages the squared differences: predictions (2, 4) against targets (3, 2) give errors -1 and 2, squares 1 and 4, so MSE = 2.5. Squaring makes every error positive and punishes large errors more. Classifiers usually use cross-entropy instead.

## gradient-descent | Gradient descent
Gradient descent repeats w ← w - η · ∂L/∂w for every weight, where η is the learning rate. With w = 2, η = 0.1 and ∂L/∂w = 4, the new weight is 2 - 0.4 = 1.6. The minus sign moves against the gradient, the direction of steepest decrease. Too large a learning rate overshoots and can diverge; too small converges slowly.

## linear-regression | Linear regression
Linear regression models y ≈ wx + b (or w·x + b for many features) and chooses w and b to minimise the mean squared error on the training data, either in closed form or with gradient descent. A trained model y = 3x + 2 predicts 14 for x = 4. It predicts a continuous number.

## sigmoid | Sigmoid function
σ(z) = 1 / (1 + e^(-z)) maps any real number into (0, 1): σ(0) = 0.5, large positive z gives values near 1 and large negative z gives values near 0. Because its output lies between 0 and 1 it can be read as a probability. Its derivative is σ(z)(1 - σ(z)). tanh is a related curve with range (-1, 1).

## cross-entropy | Cross-entropy loss
Binary cross-entropy is L = -[y ln p + (1 - y) ln(1 - p)]. For y = 1 it is -ln p: p = 0.9 costs about 0.105, p = 0.5 costs about 0.693 and p = 0.01 costs about 4.6. Confident wrong answers are punished heavily, which suits classifiers better than MSE.

## logistic-regression | Logistic regression
Logistic regression computes p = σ(w·x + b), the probability of class 1, and predicts class 1 when p is above a threshold (usually 0.5). It is a classifier, not a method for predicting continuous values, and it is trained by minimising cross-entropy with gradient descent.

## softmax | Softmax
Softmax turns a score vector z into probabilities: softmax(z)_i = e^(z_i) / Σ_j e^(z_j). Every output is between 0 and 1 and they sum to 1. Equal scores (2, 2, 2) give (1/3, 1/3, 1/3). Adding the same constant to every score does not change the result. It generalises the sigmoid to more than two classes.

## activation-functions | Activation functions
An activation function is applied after each layer's weighted sum. ReLU(x) = max(0, x) keeps positive values and zeroes negative ones, so ReLU(-3) = 0. Sigmoid and tanh squash values into (0, 1) and (-1, 1). Non-linearity is essential: stacking purely linear layers collapses into a single linear function.

## artificial-neuron | Artificial neuron
A neuron computes z = w·x + b and outputs a = f(z) for an activation f. With w = (1, 2), b = -1 and x = (3, 1): z = 3 + 2 - 1 = 4 and ReLU(4) = 4. The weights scale each input; the bias shifts the sum before the activation.

## forward-pass | Neural network forward pass
A layer computes a = f(Wx + b), where row i of W holds neuron i's weights. With W of shape 4 × 3 and x of shape 3 × 1, Wx + b is 4 × 1: one value per neuron. The forward pass applies layers in order, each layer's output becoming the next layer's input, until the prediction and then the loss are computed.

## backpropagation | Backpropagation
Backpropagation computes ∂L/∂w for every weight by applying the chain rule from the loss backwards through the network. For L = (a - y)^2 with a = w·x: ∂L/∂a = 2(a - y) and ∂a/∂w = x, so ∂L/∂w = 2(a - y)·x. Each layer reuses the gradient arriving from the layer after it, which makes the whole computation efficient. Gradient descent then uses these gradients to update the weights.

## overfitting | Overfitting and validation
A model overfits when it learns noise in the training data: training loss keeps falling while validation loss rises. Hold out a validation set for tuning and a separate test set for a final, honest estimate on unseen data. Remedies include more data, simpler models, regularisation and early stopping.
