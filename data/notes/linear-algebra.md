# Linear algebra (curated demo notes)

> Written for the Punca prototype as stand-in course notes. Replace with real APU module notes (with permission) before any real use.

## vectors | Vectors
A vector is an ordered list of numbers, such as (2, -1, 3). Add vectors component by component: (2, -1, 3) + (1, 4, -2) = (3, 3, 1). Multiplying by a scalar scales every component. The length (magnitude) of (3, 4) is sqrt(3^2 + 4^2) = 5. In ML a data point, a set of weights and a gradient are all vectors.

## dot-product | Dot product
The dot product multiplies matching components and adds the results: (1, 2, 3)·(4, 0, -1) = 4 + 0 - 3 = 1. The answer is a single number, not a vector. Geometrically a·b = |a||b|cos θ, so the dot product of two non-zero vectors is 0 exactly when they are perpendicular. A neuron's weighted sum w·x is a dot product.

## matrices | Matrices and shapes
A matrix is a grid of numbers with a shape written rows × columns: 3 rows and 2 columns is 3 × 2. Entry A_ij is in row i, column j, so in [[1, 2], [3, 4]] the entry in row 2, column 1 is 3. Keeping track of shapes prevents most bugs in neural network code.

## matrix-multiplication | Matrix multiplication
AB is defined when A's number of columns equals B's number of rows: (m × n)(n × p) gives m × p. Each entry of AB is the dot product of a row of A with a column of B: [[1, 2], [3, 4]] × [[5], [6]] = [[1·5 + 2·6], [3·5 + 4·6]] = [[17], [39]]. This is not element-by-element multiplication, and in general AB ≠ BA. A "shape mismatch" error means the inner sizes do not agree.

## transpose | Matrix transpose
The transpose A^T swaps rows and columns: entry (i, j) moves to (j, i), so a 4 × 2 matrix becomes 2 × 4 and a row vector becomes a column vector with the same entries in the same order. Transposes are used to make shapes line up, for example W^T in backpropagation.
