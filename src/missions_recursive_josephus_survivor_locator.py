def josephus_survivor(n: int, k: int) -> int:
	"""
	Recursively determines the 0-indexed safe position among n people
	standing in a circle where every k-th person is eliminated until one remains.

	Args:
		n: Number of people (must be >= 1)
		k: Step size for elimination (must be >= 1)

	Returns:
		The 0-indexed position of the survivor

	Raises:
		ValueError: If n < 1 or k < 1
	"""
	if n < 1:
		raise ValueError("n must be at least 1")
	if k < 1:
		raise ValueError("k must be at least 1")

	if n == 1:
		return 0

	return (josephus_survivor(n - 1, k) + k) % n