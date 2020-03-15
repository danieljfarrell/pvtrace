import numpy as np
from pvtrace.geometry.transformations import (
    rotation_matrix,
    translation_matrix,
    translation_from_matrix,
)
import logging

logger = logging.getLogger(__name__)


class Transformable(object):
    """  A friendly abstraction of a coordinate system.
    
        Transformables can be incrementally translated or rotated. The rotation
        are always around the current location of the transformable, so the
        location will not be altered.
        
        For full access, transformables allow setting and getting of the `pose`
        which is the 4-by-4 homogenous transformation matrix.
    
        This is intended to be uses as a mixin.
    """

    def __init__(self, location=None):
        """
        Initialise using either a `location` point or a 4-by-4 `pose` matrix.
        
        Parameters
        ----------
        location : array_like
            Location of the node in the parent's coordinate
            system.
        pose : array_like
            The 4-by-4 homogenous transform matrix describing the pose
            of the node.

        Raises
        ------
        ValueError if both `location` and `pose` are specified.
        
        Returns
        -------
        Transformable
            The object.
        """
        super(Transformable, self).__init__()
        self._location = (
            np.zeros(3, dtype=np.float) if location is None else np.array(location)
        )
        self._pose = translation_matrix(self._location)

    @classmethod
    def from_pose(cls, new_value):
        if new_value.shape != (4, 4):
            raise ValueError("Must be a 4x4 transform matrix")
        obj = cls()
        obj.pose = new_value
        return obj

    @property
    def pose(self):
        return self._pose

    @pose.setter
    def pose(self, new_value):
        self._location = translation_from_matrix(new_value)
        self._pose = np.array(new_value)
        return self

    @property
    def location(self):
        return self._location

    @location.setter
    def location(self, new_value):
        self._location = new_value
        self._pose[0:3, 3] = np.array(new_value)
        return self

    def translate(self, vector):
        """ Apply a relative translation to the node location. Here
        the vector is defined in the parent's coordinate system.
        """
        self._location += np.array(vector)
        self._pose = np.dot(translation_matrix(vector), self._pose)
        return self

    def rotate(self, angle, axis):
        """ Apply a body rotation to the node (location will be preserved). Here 
        axis specifies a direction in the node's coordinate system.
        """
        self._pose = np.dot(
            rotation_matrix(angle, axis, point=self._location), self._pose
        )
        return self
