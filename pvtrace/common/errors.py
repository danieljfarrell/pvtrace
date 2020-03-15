# Catch all for our own errors
class AppError(Exception):
    pass


# Raised when the ray tracing algorithm has a problem
class TraceError(AppError):
    pass


# Raised when cannot compute geometrical attributes
class GeometryError(AppError):
    pass
