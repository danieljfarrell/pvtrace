"""Recorders accumulate ray statistics during tracing.

A recorder is attached to a scene node and tallies rays that interact
with it in a particular way, without storing per-ray data: memory is
proportional to the number of histogram bins, not the number of rays.
This is the engine's primary output mechanism for large simulations
(the same idea as tallies/scorers in Monte Carlo transport codes).

Counting is lossless and, by default, per distinct ray: a trapped ray
crossing the same surface several times contributes once, matching the
``DISTINCT throw_id`` semantics of the CLI count queries. The number of
raw crossings is tallied separately.

Example
-------
Count rays escaping the top face of a slab and histogram their
wavelength and exit position::

    top = Recorder(
        "top-escape",
        event="escaping",
        facet=(0, 0, 1),
        histograms=[
            Histogram("wavelength", 400, 900, 100),
            Heatmap("x", "y", (-2.5, 2.5, 50), (-2.5, 2.5, 50)),
        ],
    )
    slab = Node(name="slab", geometry=Box(...), recorders=[top])
"""

# Ray properties that can be histogrammed. Position properties (x, y, z)
# are in the local frame of the node that owns the recorder.
PROPERTIES = {
    "wavelength": 0,  # nanometers
    "angle": 1,       # radians between incident ray and surface normal
    "duration": 2,    # seconds since the ray was generated
    "pathlength": 3,  # centimetres travelled since the ray was generated
    "x": 4,
    "y": 5,
    "z": 6,
}

# Interaction selectors. Surface selectors follow the CLI count
# semantics; volume selectors fire on terminal events inside the node.
EVENTS = {
    "entering": 0,   # transmitted through the node surface from outside
    "escaping": 1,   # transmitted through the node surface from inside
    "reflected": 2,  # reflected off the node surface from outside
    "lost": 3,       # non-radiatively absorbed inside the node
    "reacted": 4,    # absorbed by a Reactor component inside the node
    "killed": 5,     # killed by the tracer inside the node
    "exit": 6,       # left the scene through this (root) node's surface
}


class Histogram:
    """1D histogram specification for a ray property."""

    def __init__(self, prop, start, stop, bins):
        if prop not in PROPERTIES:
            raise ValueError(f"Unknown property {prop!r}; use one of {sorted(PROPERTIES)}")
        if not stop > start:
            raise ValueError("Histogram range requires stop > start.")
        if bins < 1:
            raise ValueError("Histogram requires at least one bin.")
        self.prop = prop
        self.start = float(start)
        self.stop = float(stop)
        self.bins = int(bins)

    def __repr__(self):
        return f"Histogram({self.prop!r}, {self.start}, {self.stop}, {self.bins})"


class Heatmap:
    """2D histogram specification over a pair of ray properties."""

    def __init__(self, prop_a, prop_b, range_a, range_b):
        self.a = Histogram(prop_a, *range_a)
        self.b = Histogram(prop_b, *range_b)

    def __repr__(self):
        return f"Heatmap({self.a!r}, {self.b!r})"


class Recorder:
    """Tallies rays interacting with a node. See module docstring."""

    def __init__(self, name, event="entering", facet=None, atol=1e-6, histograms=None):
        """Parameters
        ----------
        name: str
            Identifier used to retrieve results.
        event: str
            One of "entering", "escaping", "reflected" (surface),
            "lost", "reacted", "killed" (volume) or "exit" (root node).
        facet: tuple of float (optional)
            Restrict a surface recorder to interactions where the
            outward surface normal matches this vector within `atol`
            per component, like the CLI --nx/--ny/--nz options.
        atol: float
            Tolerance for the facet normal comparison.
        histograms: list of Histogram or Heatmap (optional)
        """
        if event not in EVENTS:
            raise ValueError(f"Unknown event {event!r}; use one of {sorted(EVENTS)}")
        self.name = name
        self.event = event
        self.facet = None if facet is None else tuple(float(v) for v in facet)
        self.atol = float(atol)
        self.histograms = [] if histograms is None else list(histograms)
        for hist in self.histograms:
            if not isinstance(hist, (Histogram, Heatmap)):
                raise ValueError("histograms must contain Histogram or Heatmap objects.")

    def __repr__(self):
        return f"Recorder({self.name!r}, event={self.event!r})"
