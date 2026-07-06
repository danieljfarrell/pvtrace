# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True, initializedcheck=False
"""Native tracing kernel.

Traces a bundle of rays through a compiled scene (see
``pvtrace.engine.compiler``). Each ray is traced start-to-finish by one
thread; rays are independent and are distributed over an OpenMP thread
pool with ``prange``. The physics replicates
``pvtrace.algorithm.photon_tracer.step_forward`` for the supported scene
subset: same event sequence, same sampling distributions.
"""
import numpy as np
cimport numpy as cnp
from cython.parallel import prange, threadid

cnp.import_array()
from libc.math cimport (
    INFINITY,
    M_PI,
    acos,
    asin,
    cos,
    fabs,
    log,
    sin,
    sqrt,
)

# Distance tolerance, matches pvtrace.geometry.utils.EPS_ZERO
cdef double EPS = 2.220446049250313e-13
# Attenuation coefficients closer to zero than this are treated as zero,
# matching np.isclose(alpha, 0.0) in Material.penetration_depth.
cdef double ALPHA_ZERO = 1e-8
cdef double C_CM_PER_S = 2.99792458e10
cdef double KB_EV = 1.380649e-23 / 1.60217662e-19

# Event codes, must match pvtrace.light.event.Event
cdef int EV_GENERATE = 0
cdef int EV_REFLECT = 1
cdef int EV_TRANSMIT = 2
cdef int EV_ABSORB = 3
cdef int EV_NONRADIATIVE = 4
cdef int EV_SCATTER = 5
cdef int EV_EMIT = 6
cdef int EV_EXIT = 7
cdef int EV_REACT = 8
cdef int EV_KILL = 9

# Tags, must match pvtrace.engine.compiler
cdef int GEOM_BOX = 0
cdef int GEOM_SPHERE = 1
cdef int GEOM_CYLINDER = 2
cdef int SURF_FRESNEL = 0
cdef int SURF_NULL = 1
cdef int COMP_ABSORBER = 0
cdef int COMP_SCATTERER = 1
cdef int COMP_LUMINOPHORE = 2
cdef int COMP_REACTOR = 3
cdef int PHASE_ISOTROPIC = 0
cdef int PHASE_HENYEY_GREENSTEIN = 1
cdef int PHASE_CONE = 2
cdef int EMIT_KT = 0
cdef int EMIT_REDSHIFT = 1
cdef int EMIT_FULL = 2

cdef enum:
    MAX_NODES = 128
    MAX_HITS = 512  # up to 4 intersections per node


# ----------------------------------------------------------------------
# Random number generation: splitmix64-seeded xoshiro256+, one stream per
# ray so results are independent of thread scheduling.

cdef struct RNG:
    unsigned long long s0
    unsigned long long s1
    unsigned long long s2
    unsigned long long s3


cdef inline unsigned long long _splitmix64(unsigned long long* state) noexcept nogil:
    cdef unsigned long long z
    state[0] += <unsigned long long>0x9E3779B97F4A7C15
    z = state[0]
    z = (z ^ (z >> 30)) * <unsigned long long>0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * <unsigned long long>0x94D049BB133111EB
    return z ^ (z >> 31)


cdef inline void rng_seed(RNG* rng, unsigned long long seed) noexcept nogil:
    cdef unsigned long long state = seed
    rng.s0 = _splitmix64(&state)
    rng.s1 = _splitmix64(&state)
    rng.s2 = _splitmix64(&state)
    rng.s3 = _splitmix64(&state)


cdef inline unsigned long long _rotl(unsigned long long x, int k) noexcept nogil:
    return (x << k) | (x >> (64 - k))


cdef inline double rng_uniform(RNG* rng) noexcept nogil:
    """Uniform double in [0, 1)."""
    cdef unsigned long long result = rng.s0 + rng.s3
    cdef unsigned long long t = rng.s1 << 17
    rng.s2 ^= rng.s0
    rng.s3 ^= rng.s1
    rng.s1 ^= rng.s2
    rng.s0 ^= rng.s3
    rng.s2 ^= t
    rng.s3 = _rotl(rng.s3, 45)
    return (result >> 11) * (1.0 / 9007199254740992.0)


# ----------------------------------------------------------------------
# Scene tables as raw pointers so the tracing loop is pure C.

cdef struct SceneT:
    int n_nodes
    int root
    int* geom_type
    double* geom_params      # (n, 4)
    double* l2w              # (n, 16)
    double* w2l              # (n, 16)
    double* nidx
    int* surf_type
    int* comp_start
    int* comp_count
    int* comp_type
    double* comp_qy
    double* comp_tau_rad
    double* comp_tau_nr
    int* comp_phase_type
    double* comp_phase_param
    int* abs_start
    int* abs_n
    int* ems_start
    int* ems_n
    double* abs_x
    double* abs_y
    double* ems_x
    double* ems_cdf
    # Recorders (tallies)
    int n_recorders
    int total_bins
    int* rec_node
    int* rec_event
    int* rec_has_facet
    double* rec_facet        # (n_recorders, 3)
    double* rec_atol
    int* rec_hist_start
    int* rec_hist_n
    int* h_prop_a
    int* h_prop_b            # -1 for a 1D histogram
    int* h_na
    int* h_nb
    double* h_lo_a
    double* h_hi_a
    double* h_lo_b
    double* h_hi_b
    int* h_offset


# Recorder event selectors, must match pvtrace.engine.recorder.EVENTS
cdef int REC_ENTERING = 0
cdef int REC_ESCAPING = 1
cdef int REC_REFLECTED = 2
cdef int REC_LOST = 3
cdef int REC_REACTED = 4
cdef int REC_KILLED = 5
cdef int REC_EXIT = 6


cdef struct AccBase:
    # Per-thread tally accumulators; thread `tid` owns the slice
    # starting at tid * n_recorders (or tid * total_bins for bins).
    long long* distinct
    long long* cross
    double* sums             # (threads, n_recorders, 4 moments, 2)
    long long* bins          # (threads, total_bins)


cdef struct EventLog:
    unsigned char* kind
    int* hit
    int* container
    int* adjacent
    int* component
    int* source
    double* position         # (rows, 3)
    double* direction        # (rows, 3)
    double* normal           # (rows, 3)
    double* wavelength
    double* travelled
    double* duration
    int max_events


# ----------------------------------------------------------------------
# Small math helpers

cdef inline double dot3(double* a, double* b) noexcept nogil:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


cdef inline void transform_point(double* m, double* p, double* out) noexcept nogil:
    cdef int i
    for i in range(3):
        out[i] = m[i * 4] * p[0] + m[i * 4 + 1] * p[1] + m[i * 4 + 2] * p[2] + m[i * 4 + 3]


cdef inline void transform_vector(double* m, double* v, double* out) noexcept nogil:
    cdef int i
    for i in range(3):
        out[i] = m[i * 4] * v[0] + m[i * 4 + 1] * v[1] + m[i * 4 + 2] * v[2]


cdef inline double interp_clamped(double x, double* xs, double* ys, int n) noexcept nogil:
    """Linear interpolation with edge-value clamping (like np.interp)."""
    cdef int lo, hi, mid
    if n == 1:
        return ys[0]
    if x <= xs[0]:
        return ys[0]
    if x >= xs[n - 1]:
        return ys[n - 1]
    lo = 0
    hi = n - 1
    while hi - lo > 1:
        mid = (lo + hi) >> 1
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    if xs[hi] == xs[lo]:
        return ys[lo]
    return ys[lo] + (ys[hi] - ys[lo]) * (x - xs[lo]) / (xs[hi] - xs[lo])


# ----------------------------------------------------------------------
# Geometry intersections in the local frame. Directions are unit vectors
# and transforms are rigid, so local t equals world distance.

cdef inline int intersect_box(double* params, double* o, double* d, double* ts) noexcept nogil:
    cdef double lo, hi, t1, t2, inv, tmp
    cdef double tmin = -INFINITY
    cdef double tmax = INFINITY
    cdef int axis, n = 0
    for axis in range(3):
        lo = -0.5 * params[axis]
        hi = 0.5 * params[axis]
        if fabs(d[axis]) < 1e-300:
            if o[axis] < lo or o[axis] > hi:
                return 0
        else:
            inv = 1.0 / d[axis]
            t1 = (lo - o[axis]) * inv
            t2 = (hi - o[axis]) * inv
            if t1 > t2:
                tmp = t1
                t1 = t2
                t2 = tmp
            if t1 > tmin:
                tmin = t1
            if t2 < tmax:
                tmax = t2
    if tmax < tmin:
        return 0
    if tmin > EPS:
        ts[n] = tmin
        n += 1
    if tmax > EPS:
        ts[n] = tmax
        n += 1
    return n


cdef inline int intersect_sphere(double* params, double* o, double* d, double* ts) noexcept nogil:
    cdef double radius = params[0]
    cdef double a = dot3(d, d)
    cdef double b = 2.0 * dot3(d, o)
    cdef double c = dot3(o, o) - radius * radius
    cdef double disc = b * b - 4.0 * a * c
    cdef double sq, t
    cdef int n = 0
    if disc < 0.0:
        return 0
    sq = sqrt(disc)
    t = (-b - sq) / (2.0 * a)
    if t > EPS:
        ts[n] = t
        n += 1
    t = (-b + sq) / (2.0 * a)
    if t > EPS:
        ts[n] = t
        n += 1
    return n


cdef inline int intersect_cylinder(double* params, double* o, double* d, double* ts) noexcept nogil:
    """Z-axis cylinder with caps, centre at origin."""
    cdef double length = params[0]
    cdef double radius = params[1]
    cdef double half = 0.5 * length
    cdef double a = d[0] * d[0] + d[1] * d[1]
    cdef double b, c, disc, sq, t, z, x, y
    cdef int n = 0, i
    cdef double cand[4]
    cdef int ncand = 0

    if a > 1e-300:
        b = 2.0 * (o[0] * d[0] + o[1] * d[1])
        c = o[0] * o[0] + o[1] * o[1] - radius * radius
        disc = b * b - 4.0 * a * c
        if disc >= 0.0:
            sq = sqrt(disc)
            t = (-b - sq) / (2.0 * a)
            z = o[2] + t * d[2]
            if z > -half and z < half:
                cand[ncand] = t
                ncand += 1
            t = (-b + sq) / (2.0 * a)
            z = o[2] + t * d[2]
            if z > -half and z < half:
                cand[ncand] = t
                ncand += 1
    if fabs(d[2]) > 1e-300:
        t = (-half - o[2]) / d[2]
        x = o[0] + t * d[0]
        y = o[1] + t * d[1]
        if x * x + y * y <= radius * radius:
            cand[ncand] = t
            ncand += 1
        t = (half - o[2]) / d[2]
        x = o[0] + t * d[0]
        y = o[1] + t * d[1]
        if x * x + y * y <= radius * radius:
            cand[ncand] = t
            ncand += 1
    for i in range(ncand):
        if cand[i] > EPS:
            ts[n] = cand[i]
            n += 1
    return n


cdef inline int intersect_node(SceneT* S, int node, double* o, double* d, double* ts) noexcept nogil:
    cdef int gtype = S.geom_type[node]
    cdef double* params = S.geom_params + node * 4
    if gtype == GEOM_BOX:
        return intersect_box(params, o, d, ts)
    elif gtype == GEOM_SPHERE:
        return intersect_sphere(params, o, d, ts)
    else:
        return intersect_cylinder(params, o, d, ts)


cdef inline void local_normal(SceneT* S, int node, double* p, double* out) noexcept nogil:
    """Outward surface normal at local point `p`."""
    cdef int gtype = S.geom_type[node]
    cdef double* params = S.geom_params + node * 4
    cdef double best, dist, mag, half, r
    cdef int axis, best_axis, best_sign, sign
    if gtype == GEOM_BOX:
        best = INFINITY
        best_axis = 0
        best_sign = 1
        for axis in range(3):
            for sign in range(-1, 2, 2):
                dist = fabs(p[axis] - sign * 0.5 * params[axis])
                if dist < best:
                    best = dist
                    best_axis = axis
                    best_sign = sign
        out[0] = 0.0
        out[1] = 0.0
        out[2] = 0.0
        out[best_axis] = <double>best_sign
    elif gtype == GEOM_SPHERE:
        mag = sqrt(dot3(p, p))
        out[0] = p[0] / mag
        out[1] = p[1] / mag
        out[2] = p[2] / mag
    else:
        half = 0.5 * params[0]
        # np.isclose default tolerances
        if fabs(p[2] + half) <= 1e-8 + 1e-5 * fabs(half):
            out[0] = 0.0
            out[1] = 0.0
            out[2] = -1.0
        elif fabs(p[2] - half) <= 1e-8 + 1e-5 * fabs(half):
            out[0] = 0.0
            out[1] = 0.0
            out[2] = 1.0
        else:
            r = sqrt(p[0] * p[0] + p[1] * p[1])
            out[0] = p[0] / r
            out[1] = p[1] / r
            out[2] = 0.0


# ----------------------------------------------------------------------
# Optics

cdef inline double fresnel_reflectivity(double angle, double n1, double n2) noexcept nogil:
    cdef double c, s, k, rs1, rs2, rs, rp1, rp2, rp
    if n2 < n1 and angle > asin(n2 / n1):
        return 1.0
    c = cos(angle)
    s = sin(angle)
    k = sqrt(1.0 - (n1 / n2 * s) ** 2)
    rs1 = n1 * c - n2 * k
    rs2 = n1 * c + n2 * k
    rs = (rs1 / rs2) ** 2
    rp1 = n1 * k - n2 * c
    rp2 = n1 * k + n2 * c
    rp = (rp1 / rp2) ** 2
    return 0.5 * (rs + rp)


cdef inline void specular_reflect(double* d, double* normal, double* out) noexcept nogil:
    cdef double n[3]
    cdef double dd
    cdef int i
    for i in range(3):
        n[i] = normal[i]
    if dot3(n, d) < 0.0:
        for i in range(3):
            n[i] = -n[i]
    dd = dot3(n, d)
    for i in range(3):
        out[i] = d[i] - 2.0 * dd * n[i]


cdef inline void fresnel_refract(double* d, double* normal, double n1, double n2, double* out) noexcept nogil:
    """`normal` must already be flipped to point along the ray direction."""
    cdef double n = n1 / n2
    cdef double dd = dot3(d, normal)
    cdef double c = sqrt(1.0 - n * n * (1.0 - dd * dd))
    cdef double sign = 1.0
    cdef int i
    if dd < 0.0:
        sign = -1.0
    for i in range(3):
        out[i] = n * d[i] + sign * (c - sign * n * dd) * normal[i]


cdef inline void sample_sphere_direction(double theta, double phi, double* out) noexcept nogil:
    out[0] = sin(theta) * cos(phi)
    out[1] = sin(theta) * sin(phi)
    out[2] = cos(theta)


cdef inline void sample_phase(int phase_type, double phase_param, RNG* rng, double* out) noexcept nogil:
    cdef double g1, g2, phi, mu, theta, s, g
    if phase_type == PHASE_HENYEY_GREENSTEIN and fabs(phase_param) >= EPS:
        g = phase_param
        g1 = rng_uniform(rng)
        s = 2.0 * g1 - 1.0
        mu = 1.0 / (2.0 * g) * (1.0 + g * g - ((1.0 - g * g) / (1.0 + g * s)) ** 2)
        phi = 2.0 * M_PI * rng_uniform(rng)
        theta = acos(mu)
    elif phase_type == PHASE_CONE:
        g1 = rng_uniform(rng)
        g2 = rng_uniform(rng)
        theta = asin(sqrt(g1) * sin(phase_param))
        phi = 2.0 * M_PI * g2
    else:
        # Isotropic (also Henyey-Greenstein in the g -> 0 limit)
        g1 = rng_uniform(rng)
        g2 = rng_uniform(rng)
        phi = 2.0 * M_PI * g1
        mu = 2.0 * g2 - 1.0
        theta = acos(mu)
    sample_sphere_direction(theta, phi, out)


# ----------------------------------------------------------------------
# Recorders (tallies)

cdef inline double prop_value(int prop, double wavelength, double angle,
                              double duration, double travelled,
                              double* lpos) noexcept nogil:
    """Value of a histogrammable ray property (ids match recorder.PROPERTIES)."""
    if prop == 0:
        return wavelength
    elif prop == 1:
        return angle
    elif prop == 2:
        return duration
    elif prop == 3:
        return travelled
    elif prop == 4:
        return lpos[0]
    elif prop == 5:
        return lpos[1]
    return lpos[2]


cdef inline void tally(SceneT* S, AccBase* AB, int tid, int sel, int node,
                       unsigned long long* mask, double* wnormal,
                       double* lpos, double angle, double wavelength,
                       double travelled, double duration) noexcept nogil:
    """Accumulate this interaction into matching recorders.

    Counts, moments and histograms are per distinct ray (first matching
    interaction only, tracked in `mask`); raw crossings are tallied
    separately.
    """
    cdef long long* distinct = AB.distinct + tid * S.n_recorders
    cdef long long* cross = AB.cross + tid * S.n_recorders
    cdef double* sums = AB.sums + tid * S.n_recorders * 8
    cdef long long* bins = AB.bins + tid * S.total_bins
    cdef int r, h, ia, ib
    cdef double va, vb
    for r in range(S.n_recorders):
        if S.rec_node[r] != node or S.rec_event[r] != sel:
            continue
        if S.rec_has_facet[r] != 0:
            if wnormal == NULL:
                continue
            if fabs(S.rec_facet[r * 3] - wnormal[0]) > S.rec_atol[r]:
                continue
            if fabs(S.rec_facet[r * 3 + 1] - wnormal[1]) > S.rec_atol[r]:
                continue
            if fabs(S.rec_facet[r * 3 + 2] - wnormal[2]) > S.rec_atol[r]:
                continue
        cross[r] += 1
        if mask[0] & (<unsigned long long>1 << r):
            continue
        mask[0] |= (<unsigned long long>1 << r)
        distinct[r] += 1
        sums[r * 8 + 0] += wavelength
        sums[r * 8 + 1] += wavelength * wavelength
        sums[r * 8 + 2] += angle
        sums[r * 8 + 3] += angle * angle
        sums[r * 8 + 4] += duration
        sums[r * 8 + 5] += duration * duration
        sums[r * 8 + 6] += travelled
        sums[r * 8 + 7] += travelled * travelled
        for h in range(S.rec_hist_start[r], S.rec_hist_start[r] + S.rec_hist_n[r]):
            va = prop_value(S.h_prop_a[h], wavelength, angle, duration,
                            travelled, lpos)
            ia = <int>((va - S.h_lo_a[h]) / (S.h_hi_a[h] - S.h_lo_a[h]) * S.h_na[h])
            if ia < 0 or ia >= S.h_na[h]:
                continue
            if S.h_prop_b[h] < 0:
                bins[S.h_offset[h] + ia] += 1
            else:
                vb = prop_value(S.h_prop_b[h], wavelength, angle, duration,
                                travelled, lpos)
                ib = <int>((vb - S.h_lo_b[h]) / (S.h_hi_b[h] - S.h_lo_b[h]) * S.h_nb[h])
                if ib < 0 or ib >= S.h_nb[h]:
                    continue
                bins[S.h_offset[h] + ia * S.h_nb[h] + ib] += 1


# ----------------------------------------------------------------------
# Event recording

cdef inline void record(
    EventLog* elog,
    long base,
    int* count,
    int kind,
    int hit,
    int container,
    int adjacent,
    int component,
    int source,
    double* pos,
    double* direction,
    double* normal,
    double wavelength,
    double travelled,
    double duration,
) noexcept nogil:
    cdef long row
    cdef int i
    if base < 0 or count[0] >= elog.max_events:
        return
    row = base + count[0]
    elog.kind[row] = <unsigned char>kind
    elog.hit[row] = hit
    elog.container[row] = container
    elog.adjacent[row] = adjacent
    elog.component[row] = component
    elog.source[row] = source
    for i in range(3):
        elog.position[row * 3 + i] = pos[i]
        elog.direction[row * 3 + i] = direction[i]
        elog.normal[row * 3 + i] = normal[i] if normal != NULL else 0.0
    elog.wavelength[row] = wavelength
    elog.travelled[row] = travelled
    elog.duration[row] = duration
    count[0] += 1


# ----------------------------------------------------------------------
# Main per-ray trace, replicating photon_tracer.step_forward.

cdef int trace_one(
    SceneT* S,
    EventLog* elog,
    long base,
    AccBase* AB,
    int tid,
    double* pos,
    double* direction,
    double wavelength,
    unsigned long long seed,
    int maxsteps,
    int emit_method,
) noexcept nogil:
    cdef RNG rng
    cdef int count = 0, nevents = 0
    cdef int i, k, node, nhits, nlocal
    cdef double travelled = 0.0
    cdef double duration = 0.0
    cdef int source = -1
    cdef unsigned long long rmask = 0
    cdef int sel

    cdef double hit_t[MAX_HITS]
    cdef int hit_node[MAX_HITS]
    cdef int node_hits[MAX_NODES]
    cdef double node_min_t[MAX_NODES]
    cdef double local_o[3]
    cdef double local_d[3]
    cdef double local_p[3]
    cdef double ts[8]
    cdef double nrm_local[3]
    cdef double nrm[3]
    cdef double nrm_flipped[3]
    cdef double new_dir[3]

    cdef int hit, container, adjacent, first, second
    cdef double t0, t1, best
    cdef double n_container, n1, n2, alpha, depth, u, r, angle, ddot
    cdef int comp, cbase, ccount, ctype
    cdef double total, target, running
    cdef double e_nm, e_ev, p1, gamma
    cdef double* ax
    cdef double* ay
    cdef int an

    rng_seed(&rng, seed)

    record(elog, base, &nevents, EV_GENERATE, -1, -1, -1, -1, source,
           pos, direction, NULL, wavelength, travelled, duration)

    while True:
        count += 1

        # Kill the ray when its event budget is exhausted rather than
        # silently dropping events (leave room for the KILL record).
        if base >= 0 and nevents >= elog.max_events - 1:
            record(elog, base, &nevents, EV_KILL, -1, -1, -1, -1, source,
                   pos, direction, NULL, wavelength, travelled, duration)
            break

        # --- next_hit: intersect every node ---------------------------
        nhits = 0
        for node in range(S.n_nodes):
            node_hits[node] = 0
            node_min_t[node] = INFINITY
            transform_point(S.w2l + node * 16, pos, local_o)
            transform_vector(S.w2l + node * 16, direction, local_d)
            nlocal = intersect_node(S, node, local_o, local_d, ts)
            for k in range(nlocal):
                if nhits < MAX_HITS:
                    hit_t[nhits] = ts[k]
                    hit_node[nhits] = node
                    nhits += 1
                node_hits[node] += 1
                if ts[k] < node_min_t[node]:
                    node_min_t[node] = ts[k]
        if nhits == 0:
            break

        # Nearest and second nearest intersections
        first = 0
        for i in range(1, nhits):
            if hit_t[i] < hit_t[first]:
                first = i
        second = -1
        for i in range(nhits):
            if i != first:
                if second < 0 or hit_t[i] < hit_t[second]:
                    second = i
        hit = hit_node[first]
        t0 = hit_t[first]

        if nhits == 1:
            container = hit
            adjacent = -1
        else:
            # Container: node with exactly one forward intersection that
            # is closest to the ray origin (photon_tracer.find_container).
            container = -1
            best = INFINITY
            for node in range(S.n_nodes):
                if node_hits[node] == 1 and node_min_t[node] < best:
                    best = node_min_t[node]
                    container = node
            if container < 0:
                container = hit
            if container == hit:
                adjacent = hit_node[second]
            else:
                adjacent = hit

        if count > maxsteps:
            record(elog, base, &nevents, EV_KILL, -1, container, -1, -1, source,
                   pos, direction, NULL, wavelength, travelled, duration)
            if S.n_recorders > 0:
                transform_point(S.w2l + container * 16, pos, local_p)
                tally(S, AB, tid, REC_KILLED, container, &rmask, NULL,
                      local_p, 0.0, wavelength, travelled, duration)
            break

        n_container = S.nidx[container]

        # --- exit through the root boundary ---------------------------
        if hit == S.root:
            for i in range(3):
                pos[i] = pos[i] + direction[i] * t0
            travelled += t0
            duration += t0 * n_container / C_CM_PER_S
            record(elog, base, &nevents, EV_EXIT, hit, container, adjacent, -1, source,
                   pos, direction, NULL, wavelength, travelled, duration)
            if S.n_recorders > 0:
                transform_point(S.w2l + hit * 16, pos, local_p)
                local_normal(S, hit, local_p, nrm_local)
                transform_vector(S.l2w + hit * 16, nrm_local, nrm)
                ddot = fabs(dot3(nrm, direction))
                if ddot > 1.0:
                    ddot = 1.0
                tally(S, AB, tid, REC_EXIT, hit, &rmask, nrm,
                      local_p, acos(ddot), wavelength, travelled, duration)
            break

        # --- volume absorption ----------------------------------------
        cbase = S.comp_start[container]
        ccount = S.comp_count[container]
        alpha = 0.0
        for k in range(ccount):
            comp = cbase + k
            alpha += interp_clamped(
                wavelength,
                S.abs_x + S.abs_start[comp],
                S.abs_y + S.abs_start[comp],
                S.abs_n[comp],
            )
        depth = INFINITY
        if alpha > ALPHA_ZERO:
            depth = -log(1.0 - rng_uniform(&rng)) / alpha

        if depth < t0:
            for i in range(3):
                pos[i] = pos[i] + direction[i] * depth
            travelled += depth
            duration += depth * n_container / C_CM_PER_S

            # Select component in proportion to attenuation coefficient
            target = rng_uniform(&rng) * alpha
            running = 0.0
            comp = cbase
            for k in range(ccount):
                running += interp_clamped(
                    wavelength,
                    S.abs_x + S.abs_start[cbase + k],
                    S.abs_y + S.abs_start[cbase + k],
                    S.abs_n[cbase + k],
                )
                if target <= running:
                    comp = cbase + k
                    break

            record(elog, base, &nevents, EV_ABSORB, -1, container, -1, comp, source,
                   pos, direction, NULL, wavelength, travelled, duration)

            ctype = S.comp_type[comp]
            if (ctype == COMP_SCATTERER or ctype == COMP_LUMINOPHORE) and \
                    rng_uniform(&rng) < S.comp_qy[comp]:
                # Radiative: re-emit with new direction (and wavelength)
                sample_phase(S.comp_phase_type[comp], S.comp_phase_param[comp],
                             &rng, new_dir)
                for i in range(3):
                    direction[i] = new_dir[i]
                source = comp
                if ctype == COMP_LUMINOPHORE:
                    ax = S.ems_x + S.ems_start[comp]
                    ay = S.ems_cdf + S.ems_start[comp]
                    an = S.ems_n[comp]
                    if emit_method == EMIT_FULL:
                        p1 = 0.0
                    else:
                        e_nm = wavelength
                        if emit_method == EMIT_KT:
                            e_ev = 1240.0 / e_nm + 1.5 * KB_EV * 300.0
                            e_nm = 1240.0 / e_ev
                        p1 = interp_clamped(e_nm, ax, ay, an)
                    gamma = p1 + (1.0 - p1) * rng_uniform(&rng)
                    wavelength = interp_clamped(gamma, ay, ax, an)
                    if S.comp_tau_rad[comp] > 0.0:
                        duration += -log(1.0 - rng_uniform(&rng)) * S.comp_tau_rad[comp]
                    record(elog, base, &nevents, EV_EMIT, -1, container, -1, comp, source,
                           pos, direction, NULL, wavelength, travelled, duration)
                else:
                    record(elog, base, &nevents, EV_SCATTER, -1, container, -1, comp, source,
                           pos, direction, NULL, wavelength, travelled, duration)
                continue
            else:
                if S.comp_tau_nr[comp] > 0.0:
                    duration += -log(1.0 - rng_uniform(&rng)) * S.comp_tau_nr[comp]
                if ctype == COMP_REACTOR:
                    record(elog, base, &nevents, EV_REACT, -1, container, -1, comp, source,
                           pos, direction, NULL, wavelength, travelled, duration)
                    sel = REC_REACTED
                else:
                    record(elog, base, &nevents, EV_NONRADIATIVE, -1, container, -1, comp, source,
                           pos, direction, NULL, wavelength, travelled, duration)
                    sel = REC_LOST
                if S.n_recorders > 0:
                    transform_point(S.w2l + container * 16, pos, local_p)
                    tally(S, AB, tid, sel, container, &rmask, NULL,
                          local_p, 0.0, wavelength, travelled, duration)
                break

        # --- surface interaction --------------------------------------
        for i in range(3):
            pos[i] = pos[i] + direction[i] * t0
        travelled += t0
        duration += t0 * n_container / C_CM_PER_S

        if adjacent < 0:
            # Should not happen in a well-formed scene: the only single
            # intersection surface is the root, handled above.
            record(elog, base, &nevents, EV_KILL, hit, container, -1, -1, source,
                   pos, direction, NULL, wavelength, travelled, duration)
            break

        # Outward surface normal in the world frame; the incidence angle
        # is measured between the incident direction and the normal
        # flipped to point along it.
        transform_point(S.w2l + hit * 16, pos, local_p)
        local_normal(S, hit, local_p, nrm_local)
        transform_vector(S.l2w + hit * 16, nrm_local, nrm)
        for i in range(3):
            nrm_flipped[i] = nrm[i]
        if dot3(nrm_flipped, direction) < 0.0:
            for i in range(3):
                nrm_flipped[i] = -nrm_flipped[i]
        ddot = dot3(nrm_flipped, direction)
        if ddot > 1.0:
            ddot = 1.0
        elif ddot < -1.0:
            ddot = -1.0
        angle = acos(ddot)

        r = 0.0
        if S.surf_type[hit] == SURF_FRESNEL:
            n1 = S.nidx[container]
            n2 = S.nidx[adjacent]
            r = fresnel_reflectivity(angle, n1, n2)

        u = 1.0
        if r > 0.0:
            u = rng_uniform(&rng)
        if u < r:
            specular_reflect(direction, nrm, new_dir)
            for i in range(3):
                direction[i] = new_dir[i]
            record(elog, base, &nevents, EV_REFLECT, hit, container, adjacent, -1, source,
                   pos, direction, nrm, wavelength, travelled, duration)
            if S.n_recorders > 0 and container != hit:
                tally(S, AB, tid, REC_REFLECTED, hit, &rmask, nrm,
                      local_p, angle, wavelength, travelled, duration)
            continue
        else:
            if S.surf_type[hit] == SURF_FRESNEL:
                fresnel_refract(direction, nrm_flipped, n1, n2, new_dir)
                for i in range(3):
                    direction[i] = new_dir[i]
            record(elog, base, &nevents, EV_TRANSMIT, hit, container, adjacent, -1, source,
                   pos, direction, nrm, wavelength, travelled, duration)
            if S.n_recorders > 0:
                sel = REC_ESCAPING if container == hit else REC_ENTERING
                tally(S, AB, tid, sel, hit, &rmask, nrm,
                      local_p, angle, wavelength, travelled, duration)
            continue

    return nevents


# ----------------------------------------------------------------------
# Python entry point

def trace_bundle(
    compiled,
    cnp.ndarray[cnp.float64_t, ndim=2] positions,
    cnp.ndarray[cnp.float64_t, ndim=2] directions,
    cnp.ndarray[cnp.float64_t, ndim=1] wavelengths,
    unsigned long long seed,
    int maxsteps,
    int max_events,
    int emit_method,
    int num_threads,
    long record_every,
):
    """Trace a bundle of rays and return packed event arrays and tallies.

    Every `record_every`-th ray gets a full event history (all rays when
    1, none when 0); recorders tally every ray regardless. The returned
    dict contains per-recorded-ray event counts, flat per-event fields
    (the row for event `k` of recorded ray `j` is `j * max_events + k`)
    and the merged recorder accumulators.
    """
    cdef long n = positions.shape[0]
    cdef long n_recorded = 0
    if record_every > 0:
        n_recorded = (n + record_every - 1) // record_every
    cdef long rows = n_recorded * max_events

    if compiled.geom_type.shape[0] > MAX_NODES:
        raise ValueError(f"Engine supports at most {MAX_NODES} geometry nodes.")

    # Keep references so the pointers below stay valid
    cdef cnp.ndarray[cnp.int32_t, ndim=1] geom_type = np.ascontiguousarray(compiled.geom_type)
    cdef cnp.ndarray[cnp.float64_t, ndim=2] geom_params = np.ascontiguousarray(compiled.geom_params)
    cdef cnp.ndarray[cnp.float64_t, ndim=3] l2w = np.ascontiguousarray(compiled.local_to_world)
    cdef cnp.ndarray[cnp.float64_t, ndim=3] w2l = np.ascontiguousarray(compiled.world_to_local)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] nidx = np.ascontiguousarray(compiled.refractive_index)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] surf_type = np.ascontiguousarray(compiled.surface_type)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] comp_start = np.ascontiguousarray(compiled.comp_start)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] comp_count = np.ascontiguousarray(compiled.comp_count)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] comp_type = np.ascontiguousarray(compiled.comp_type)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] comp_qy = np.ascontiguousarray(compiled.comp_qy)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] comp_tau_rad = np.ascontiguousarray(compiled.comp_tau_rad)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] comp_tau_nr = np.ascontiguousarray(compiled.comp_tau_nr)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] comp_phase_type = np.ascontiguousarray(compiled.comp_phase_type)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] comp_phase_param = np.ascontiguousarray(compiled.comp_phase_param)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] abs_start = np.ascontiguousarray(compiled.comp_abs_start)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] abs_n = np.ascontiguousarray(compiled.comp_abs_n)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ems_start = np.ascontiguousarray(compiled.comp_ems_start)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ems_n = np.ascontiguousarray(compiled.comp_ems_n)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] abs_x = np.ascontiguousarray(compiled.abs_x)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] abs_y = np.ascontiguousarray(compiled.abs_y)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] ems_x = np.ascontiguousarray(compiled.ems_x)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] ems_cdf = np.ascontiguousarray(compiled.ems_cdf)

    cdef SceneT S
    S.n_nodes = <int>geom_type.shape[0]
    S.root = <int>compiled.root_id
    S.geom_type = <int*>geom_type.data
    S.geom_params = <double*>geom_params.data
    S.l2w = <double*>l2w.data
    S.w2l = <double*>w2l.data
    S.nidx = <double*>nidx.data
    S.surf_type = <int*>surf_type.data
    S.comp_start = <int*>comp_start.data
    S.comp_count = <int*>comp_count.data
    S.comp_type = <int*>comp_type.data
    S.comp_qy = <double*>comp_qy.data
    S.comp_tau_rad = <double*>comp_tau_rad.data
    S.comp_tau_nr = <double*>comp_tau_nr.data
    S.comp_phase_type = <int*>comp_phase_type.data
    S.comp_phase_param = <double*>comp_phase_param.data
    S.abs_start = <int*>abs_start.data
    S.abs_n = <int*>abs_n.data
    S.ems_start = <int*>ems_start.data
    S.ems_n = <int*>ems_n.data
    S.abs_x = <double*>abs_x.data
    S.abs_y = <double*>abs_y.data
    S.ems_x = <double*>ems_x.data
    S.ems_cdf = <double*>ems_cdf.data

    # Recorder tables
    cdef cnp.ndarray[cnp.int32_t, ndim=1] rec_node = np.ascontiguousarray(compiled.rec_node)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] rec_event = np.ascontiguousarray(compiled.rec_event)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] rec_has_facet = np.ascontiguousarray(compiled.rec_has_facet)
    cdef cnp.ndarray[cnp.float64_t, ndim=2] rec_facet = np.ascontiguousarray(compiled.rec_facet)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] rec_atol = np.ascontiguousarray(compiled.rec_atol)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] rec_hist_start = np.ascontiguousarray(compiled.rec_hist_start)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] rec_hist_n = np.ascontiguousarray(compiled.rec_hist_n)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] h_prop_a = np.ascontiguousarray(compiled.hist_prop_a)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] h_prop_b = np.ascontiguousarray(compiled.hist_prop_b)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] h_na = np.ascontiguousarray(compiled.hist_na)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] h_nb = np.ascontiguousarray(compiled.hist_nb)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] h_lo_a = np.ascontiguousarray(compiled.hist_lo_a)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] h_hi_a = np.ascontiguousarray(compiled.hist_hi_a)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] h_lo_b = np.ascontiguousarray(compiled.hist_lo_b)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] h_hi_b = np.ascontiguousarray(compiled.hist_hi_b)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] h_offset = np.ascontiguousarray(compiled.hist_offset)

    S.n_recorders = <int>rec_node.shape[0]
    S.total_bins = <int>compiled.total_bins
    S.rec_node = <int*>rec_node.data
    S.rec_event = <int*>rec_event.data
    S.rec_has_facet = <int*>rec_has_facet.data
    S.rec_facet = <double*>rec_facet.data
    S.rec_atol = <double*>rec_atol.data
    S.rec_hist_start = <int*>rec_hist_start.data
    S.rec_hist_n = <int*>rec_hist_n.data
    S.h_prop_a = <int*>h_prop_a.data
    S.h_prop_b = <int*>h_prop_b.data
    S.h_na = <int*>h_na.data
    S.h_nb = <int*>h_nb.data
    S.h_lo_a = <double*>h_lo_a.data
    S.h_hi_a = <double*>h_hi_a.data
    S.h_lo_b = <double*>h_lo_b.data
    S.h_hi_b = <double*>h_hi_b.data
    S.h_offset = <int*>h_offset.data

    # Per-thread tally accumulators (merged after tracing)
    cdef int nthr = max(1, num_threads)
    cdef int nrec = max(1, S.n_recorders)
    cdef int nbins = max(1, S.total_bins)
    cdef cnp.ndarray[cnp.int64_t, ndim=2] acc_distinct = np.zeros((nthr, nrec), dtype=np.int64)
    cdef cnp.ndarray[cnp.int64_t, ndim=2] acc_cross = np.zeros((nthr, nrec), dtype=np.int64)
    cdef cnp.ndarray[cnp.float64_t, ndim=2] acc_sums = np.zeros((nthr, nrec * 8), dtype=np.float64)
    cdef cnp.ndarray[cnp.int64_t, ndim=2] acc_bins = np.zeros((nthr, nbins), dtype=np.int64)

    cdef AccBase AB
    AB.distinct = <long long*>acc_distinct.data
    AB.cross = <long long*>acc_cross.data
    AB.sums = <double*>acc_sums.data
    AB.bins = <long long*>acc_bins.data

    # Event log output arrays
    cdef cnp.ndarray[cnp.uint8_t, ndim=1] ev_kind = np.zeros(rows, dtype=np.uint8)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ev_hit = np.full(rows, -1, dtype=np.int32)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ev_container = np.full(rows, -1, dtype=np.int32)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ev_adjacent = np.full(rows, -1, dtype=np.int32)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ev_component = np.full(rows, -1, dtype=np.int32)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ev_source = np.full(rows, -1, dtype=np.int32)
    cdef cnp.ndarray[cnp.float64_t, ndim=2] ev_position = np.zeros((rows, 3), dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=2] ev_direction = np.zeros((rows, 3), dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=2] ev_normal = np.zeros((rows, 3), dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] ev_wavelength = np.zeros(rows, dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] ev_travelled = np.zeros(rows, dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] ev_duration = np.zeros(rows, dtype=np.float64)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] counts = np.zeros(max(n_recorded, 1), dtype=np.int32)

    cdef EventLog elog
    elog.kind = <unsigned char*>ev_kind.data
    elog.hit = <int*>ev_hit.data
    elog.container = <int*>ev_container.data
    elog.adjacent = <int*>ev_adjacent.data
    elog.component = <int*>ev_component.data
    elog.source = <int*>ev_source.data
    elog.position = <double*>ev_position.data
    elog.direction = <double*>ev_direction.data
    elog.normal = <double*>ev_normal.data
    elog.wavelength = <double*>ev_wavelength.data
    elog.travelled = <double*>ev_travelled.data
    elog.duration = <double*>ev_duration.data
    elog.max_events = max_events

    cdef cnp.ndarray[cnp.float64_t, ndim=2] pos_work = np.ascontiguousarray(positions).copy()
    cdef cnp.ndarray[cnp.float64_t, ndim=2] dir_work = np.ascontiguousarray(directions).copy()
    cdef cnp.ndarray[cnp.float64_t, ndim=1] wav_work = np.ascontiguousarray(wavelengths)
    cdef double* posp = <double*>pos_work.data
    cdef double* dirp = <double*>dir_work.data
    cdef double* wavp = <double*>wav_work.data
    cdef int* countp = <int*>counts.data

    cdef long i, base
    cdef int tid, nev
    with nogil:
        for i in prange(n, num_threads=num_threads, schedule="dynamic", chunksize=64):
            tid = threadid()
            if record_every > 0 and i % record_every == 0:
                base = (i // record_every) * max_events
            else:
                base = -1
            nev = trace_one(
                &S,
                &elog,
                base,
                &AB,
                tid,
                posp + i * 3,
                dirp + i * 3,
                wavp[i],
                seed + <unsigned long long>i,
                maxsteps,
                emit_method,
            )
            if base >= 0:
                countp[i // record_every] = nev

    return {
        "counts": counts[:n_recorded],
        "rec_distinct": acc_distinct.sum(axis=0)[: S.n_recorders],
        "rec_crossings": acc_cross.sum(axis=0)[: S.n_recorders],
        "rec_sums": acc_sums.sum(axis=0)[: S.n_recorders * 8].reshape(S.n_recorders, 4, 2),
        "rec_bins": acc_bins.sum(axis=0)[: S.total_bins],
        "kind": ev_kind,
        "hit": ev_hit,
        "container": ev_container,
        "adjacent": ev_adjacent,
        "component": ev_component,
        "source": ev_source,
        "position": ev_position,
        "direction": ev_direction,
        "normal": ev_normal,
        "wavelength": ev_wavelength,
        "travelled": ev_travelled,
        "duration": ev_duration,
    }
