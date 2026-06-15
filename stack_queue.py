class Stack:
    def __init__(self):
        self._items = []

    def push(self, item):
        self._items.append(item)

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from empty stack")
        return self._items.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty stack")
        return self._items[-1]

    def is_empty(self):
        return len(self._items) == 0

    def size(self):
        return len(self._items)


class Queue:
    def __init__(self):
        self._in_stack = Stack()
        self._out_stack = Stack()

    def enqueue(self, item):
        self._in_stack.push(item)

    def dequeue(self):
        if self.is_empty():
            raise IndexError("dequeue from empty queue")
        if self._out_stack.is_empty():
            while not self._in_stack.is_empty():
                self._out_stack.push(self._in_stack.pop())
        return self._out_stack.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty queue")
        if self._out_stack.is_empty():
            while not self._in_stack.is_empty():
                self._out_stack.push(self._in_stack.pop())
        return self._out_stack.peek()

    def is_empty(self):
        return self._in_stack.is_empty()

    def size(self):
        return self._in_stack.size() + self._out_stack.size()


class MinStack:
    def __init__(self):
        self._stack = Stack()
        self._min_stack = Stack()

    def push(self, item):
        self._stack.push(item)
        if self._min_stack.is_empty() or item <= self._min_stack.peek():
            self._min_stack.push(item)

    def pop(self):
        if self._stack.is_empty():
            raise IndexError("pop from empty MinStack")
        value = self._stack.pop()
        if value == self._min_stack.peek():
            self._min_stack.pop()
        return value

    def peek(self):
        if self._stack.is_empty():
            raise IndexError("peek from empty MinStack")
        return self._stack.peek()

    def get_min(self):
        if self._min_stack.is_empty():
            raise IndexError("get_min from empty MinStack")
        return self._min_stack.peek()

    def is_empty(self):
        return self._stack.is_empty()

    def size(self):
        return self._stack.size()


def is_balanced_brackets(s: str) -> bool:
    pairs = {')': '(', ']': '[', '}': '{'}
    opening = set(pairs.values())
    stack = Stack()
    for ch in s:
        if ch in opening:
            stack.push(ch)
        elif ch in pairs:
            if stack.is_empty() or stack.pop() != pairs[ch]:
                return False
    return stack.is_empty()
