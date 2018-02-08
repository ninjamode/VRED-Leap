"""
Mode detailled collision callbacks for VRED.

3 events:
- start = once called on collision start
- touch = called while colliding
- exit = once called after colliding

You can attach multiple callbacks to each event.
Nodes used while constructing the Collider will be passed to the method as a tuple in original order.
Callback method singature is: method((a, b)).

Usage:
a = findNode("a")
b = findNode("b")
collider = Collider(a, b)
collider.start.append(my_start_method)
collider.exit.append(lambda x: do_with_nodes(x))

See also Leap example scene
"""


class Collider(vrAEBase):
    """ More detailled collision callbacks for VRED """

    def __init__(self, a, b):
        vrAEBase.__init__(self)
        self.a = a
        self.b = b
        self.timer = 0
        self.timeout = 2

        self.start = []
        self.touch = []
        self.exit = []

        self.vrc = vrCollision([a], [b])
        self.vrc.connect(self.collided)
        self.first_col = not self.colliding()

    def colliding(self):
        return self.vrc.isColliding()

    def enable(state):
        self.vrc.setActive(state)

    def collided(self):
        if self.first_col:
            for cbs in self.start:
                if callable(cbs):
                    cbs((self.a, self.b))
                    self.addLoop()
        else:
            for cbt in self.touch:
                if callable(cbt):
                    cbt((self.a, self.b))

        self.first_col = False
        self.timer = 0

    def loop(self):
        self.timer += 1
        if self.timer > self.timeout:
            for cbe in self.exit:
                if callable(cbe):
                    cbe((self.a, self.b))
            self.subLoop()
            self.first_col = True
            self.timer = 0
