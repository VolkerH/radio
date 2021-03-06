""" Auxiliary functions for mask-creation """

import numpy as np
from numba import njit


@njit(nogil=True)
def create_mask_reg_jit(masks, start, end):
    """ Jit-decorated function for fast computation of masks by regression data.

    This function is usually called inside create_mask_reg function.
    """
    num_items = start.shape[0]
    for i in range(num_items):
        masks[i,
              start[i, 0]: end[i, 0],
              start[i, 1]: end[i, 1],
              start[i, 2]: end[i, 2]] = 1.
    return masks


def create_mask_reg(centers, sizes, probs, crop_shape, threshold):
    """ Create mask by data contained in predictions of regression model. """
    n_items = centers.shape[0]
    masks_array = np.zeros(shape=(n_items, *crop_shape), dtype=np.float)
    _crop_shape = np.asarray(crop_shape)

    start_pixels = np.rint(np.clip(centers - sizes / 2, 0, 1) * _crop_shape).astype(np.int)
    end_pixels = np.rint(np.clip(centers + sizes / 2, 0, 1) * _crop_shape).astype(np.int)
    positions = np.array([p > threshold for p in probs])

    masks_array[positions, ...] = create_mask_reg_jit(masks_array[positions, ...],
                                                      start_pixels[positions, ...],
                                                      end_pixels[positions, ...])
    return masks_array


@njit(nogil=True)
def insert_cropped(where, what, origin):
    """ Insert `what` into `where` starting from `origin`

    Parameters
    ----------
    where : ndarray
        3d-array, in which to insert new data.
    what : ndarray
        3d-array, which is inserted.
    origin : ndarray
        starting positions of insertion along (z,y,x).

    Returns
    -------
    None
        changes `where` array.

    Notes
    -----
    What-array is cropped if origin<0 or what-array
    is too large to be put in where-array.

    Examples
    --------
        where = np.zeros(shape=(3, 3, 3), dtype='int')
        what = np.ones(shape=(2, 2, 2), dtype='int')
        origin = np.asarray([2, 2, 2])

        # after execution
        insert_cropped(where, what, origin)
        # where[2, 2, 2] = 1, other elems = 0
    """
    # shapes to arrays for convenience
    what_shape = np.array(what.shape)
    where_shape = np.array(where.shape)

    # check if there is anything to insert
    if np.any(what_shape + origin <= 0) or np.any(origin >= where_shape):
        return

    # define crop boundaries
    st_what = -np.minimum(np.zeros_like(origin), origin)
    end_what = np.minimum(where_shape - origin, what_shape)

    st_where = np.maximum(origin, np.zeros_like(origin))
    end_where = np.minimum(origin + what_shape, where_shape)

    # perform insert
    where[st_where[0]: end_where[0],
          st_where[1]: end_where[1],
          st_where[2]: end_where[2]] = what[st_what[0]: end_what[0],
                                            st_what[1]: end_what[1],
                                            st_what[2]: end_what[2]]


@njit(nogil=True)
def make_rect_mask_numba(batch_mask, start, end, nodules_start, nodules_size):
    """ Make mask using information about nodules location and sizes.

    Takes batch_masks already filled with zeros,
    `img` and `img` positions of coresponding patient's data array in batch_mask,

    Parameters
    ----------
    batch_mask : ndarray
        `masks` from batch, just initialised (filled with zeroes).
    start : ndarray
        for each nodule, start position of patient in `skyscraper` is given
        by (nodule_index, z_start, y_start, x_start)
    end : ndarray
        for each nodule, end position of patient in `skyscraper` is given
        by (nodule_index, z_start, y_start, x_start)
    nodules_start : ndarray(4,)
        array, first dim is nodule index, others (z,y,x)
        are start coordinates of nodules
        (smallest voxel with nodule).
    nodules_size : tuple, list or ndarray
        (z,y,x) shape of nodule

    """
    for i in range(nodules_start.shape[0]):
        nodule_size = nodules_size[i, :]

        nodule = np.ones((int(nodule_size[0]),
                          int(nodule_size[1]),
                          int(nodule_size[2])))

        patient_mask = batch_mask[start[i, 0]: end[i, 0],
                                  start[i, 1]: end[i, 1],
                                  start[i, 2]: end[i, 2]]
        insert_cropped(patient_mask, nodule, nodules_start[i, :])

@njit(nogil=True)
def make_ellipse_mask_numba(batch_mask, start, end, centers, radiuses):
    """ Make mask with ellipses using information about nodules location and sizes.

    Takes batch_masks already filled with zeros,
    `img` and `img` positions of coresponding patient's data array in batch_mask,

    Parameters
    ----------
    batch_mask : ndarray
        `masks` from batch, just initialised (filled with zeroes).
    start : ndarray
        for each nodule, start position of patient in `skyscraper` is given
        by (nodule_index, z_start, y_start, x_start)
    end : ndarray
        for each nodule, end position of patient in `skyscraper` is given
        by (nodule_index, z_start, y_start, x_start)
    centers : ndarray(4,)
        array, first dim is nodule index, others (z,y,x)
        are nodule centers
    radiuses : tuple, list or ndarray
        radiuses of nodules

    """
    for i in range(len(centers)): # pylint: disable=consider-using-enumerate
        center = centers[i]
        radius = radiuses[i]

        begin_x = np.maximum(0, center[0]-radius[0])
        begin_y = np.maximum(0, center[1]-radius[1])
        begin_z = np.maximum(0, center[2]-radius[2])

        end_x = np.minimum(end[i][0]-start[i][0], center[0]+radius[0]+1)
        end_y = np.minimum(end[i][1]-start[i][1], center[1]+radius[1]+1)
        end_z = np.minimum(end[i][2]-start[i][2], center[2]+radius[2]+1)

        for x in range(begin_x, end_x):
            for y in range(begin_y, end_y):
                for z in range(begin_z, end_z):
                    if (((x - center[0])/radius[0]) ** 2 +
                            ((y - center[1])/radius[1]) ** 2 + ((z - center[2])/radius[2]) ** 2 < 1):
                        batch_mask[x+start[i][0], y+start[i][1], z+start[i][2]] = 1
