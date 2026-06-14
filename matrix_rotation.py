rotate_90 = [[3,1],[4,2]]
def rotate_90(m):
    n = len(m)
    return [[m[n-1-j][i] for j in range(n)] for i in range(n)]