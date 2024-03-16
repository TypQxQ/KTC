class A:
    def __init__(self):
        self._attr = 42
    @property
    def attr(self):
        return self._attr

    @attr.setter
    def attr(self, value):
        self._attr = value

    def my_method(self):
        self.attr = 43

class B(A):
    def my_other_method(self):
        super().attr = 43
        