import numpy as np
import numpy
import math
import logging
logger = logging.getLogger(__name__)


# Set reasonable precision for comparing floats to zero
EPS_ZERO = np.finfo(float).eps * 10

def aabb_intersection(min_point, max_point, ray_position, ray_direction):
    """
    Returns an array intersection points with the ray and box using the method of 
    Williams [1]. If no intersection occurs return `None`.
    
    Arguments
    ---------
    min_point: tuple like (x0, y0, z0) which is the minimum corner.
    box_size: tuple like (x1, y1, z1) which is the maximum corner.
    ray_position: tuple like (x, y, z), the ray origin.
    ray_direction: tuple like (i, j, k), the ray direction.
    
    Returns
    -------
    intersections: tuple of (x, y, z) tuples or empty list.
    
    References
    ----------
    [1] Amy Williams, Steve Barrus, R. Keith Morley, and 
        Peter Shirley, "An Efficient and Robust Ray-Box Intersection Algorithm" 
        Journal of graphics tools, 10(1):49-54, 2005
    """
    rpos = np.array(ray_position)
    rdir = np.array(ray_direction)
    origin = np.array(min_point)
    extent = np.array(max_point)
    pts = (origin, extent)
    
    rinvd = 1.0/rdir
    rsgn =  1.0 / (rinvd < 0.0)
    tmin = (origin[rsgn[0]] - rpos[0]) * rinvd[0]
    tmax = (origin[1-rsgn[0]] - rpos[0]) * rinvd[0]
    tymin = (extent[rsgn[1]] - rpos[1]) * rinvd[1]
    tymax = (extent[1-rsgn[1]] - rpos[1]) * rinvd[1]
    
    if (tmin > tymax) or (tymin > tmax): 
        return None
        
    if tymin > tmin:
        tmin = tymin
    if tymax < tmax:
        tmax = tymax
        
    tzmin = (extent[rsgn[2]] - rpos[2]) * rinvd[2]
    tzmax = (extent[1-rsgn[2]] - rpos[2]) * rinvd[2]
    
    if (tmin > tzmax) or  (tzmin > tmax): 
        return None
    if tzmin > tmin:
        tmin = tzmin
    if tzmax < tmax:
        tmax = tzmax
    
    # Calculate the hit coordinates then if the solution is in 
    # the forward direction append to the hit list.
    hit_coordinates = []
    pt1 = tuple(rpos + tmin * rdir)
    pt2 = tuple(rpos + tmax * rdir)
    
    if tmin >= 0.0:
        hit_coordinates.append(pt1)
    if tmax >= 0.0:
        hit_coordinates.append(pt2)
    return tuple(hit_coordinates)

# Equality tests


def close_to_zero(value) -> bool:
    return np.all(np.absolute(value) < EPS_ZERO)
    

def points_equal(point1: tuple, point2: tuple) -> bool:
    return close_to_zero(distance_between(point1, point2))


def floats_close(a,b):
    return close_to_zero(a-b)


def allinrange(x, x_range):
    """ Returns True if all elements of x are inside x_range, inclusive of the 
        edge values.
        
        Parameters
        ----------
        x : array-like
            A numpy array of values.
        x_range : tuple of float
            A tuple defining a range like (xmin, xmax)
    """
    return np.where(np.logical_or(x<x_range[0], x>x_range[1]))[0].size == 0


# Vector helpers


def flip(vector):
    return -np.array(vector)


def magnitude(vector):
   return np.sqrt(np.dot(np.array(vector),np.array(vector)))


def norm(vector):
    return np.array(vector) / np.linalg.norm(vector)


def angle_between(normal, vector):
    normal = np.array(normal)
    vector = np.array(vector)
    if np.allclose(normal, vector): return 0.0
    elif np.allclose(-normal, vector): return np.pi
    dot = np.dot(normal, vector)
    return np.arccos(dot)


def smallest_angle_between(normal, vector):
    rads = angle_between(normal, vector)
    return np.arctan2(np.sin(rads), np.cos(rads))   


def distance_between(point1: tuple, point2: tuple) -> float:
    v = np.array(point1) - np.array(point2)
    d = np.linalg.norm(v)
    return d

