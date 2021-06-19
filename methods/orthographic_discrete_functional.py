import numpy as np
from scipy.sparse.linalg import lsqr
from utils import *
import pyvista as pv
from scipy.sparse import coo_matrix, vstack
import time


def generate_dx_dy_wb(normal_mask, step_size=1):
    all_depth_idx = np.zeros_like(normal_mask, dtype=np.int)
    all_depth_idx[normal_mask] = np.arange(np.sum(normal_mask))
    num_depth = np.sum(normal_mask)

    move_left_mask = np.pad(normal_mask, ((0, 0), (0, 1)), "constant", constant_values=0)[:, 1:]
    move_right_mask = np.pad(normal_mask, ((0, 0), (1, 0)), "constant", constant_values=0)[:, :-1]
    move_top_mask = np.pad(normal_mask, ((0, 1), (0, 0)), "constant", constant_values=0)[1:, :]
    move_bottom_mask = np.pad(normal_mask, ((1, 0), (0, 0)), "constant", constant_values=0)[:-1, :]

    has_left_and_right_mask = np.logical_and.reduce((move_left_mask, move_right_mask, normal_mask))
    has_only_left_mask = np.logical_and(np.logical_xor(move_left_mask, normal_mask), normal_mask)
    has_only_right_mask = np.logical_and(np.logical_xor(move_right_mask, normal_mask), normal_mask)

    has_left_and_right_mask_left = np.pad(has_left_and_right_mask, ((0, 0), (0, 1)), "constant", constant_values=0)[:, 1:]
    has_left_and_right_mask_right = np.pad(has_left_and_right_mask, ((0, 0), (1, 0)), "constant", constant_values=0)[:, :-1]

    has_only_left_mask_left = np.pad(has_only_left_mask, ((0, 0), (0, 1)), "constant", constant_values=0)[:, 1:]
    has_only_right_mask_right = np.pad(has_only_right_mask, ((0, 0), (1, 0)), "constant", constant_values=0)[:, :-1]

    row_idx = np.concatenate([all_depth_idx[has_only_left_mask].flatten(),
                              all_depth_idx[has_only_right_mask].flatten(),
                              all_depth_idx[has_left_and_right_mask].flatten(),
                              all_depth_idx[has_only_left_mask].flatten(),
                              all_depth_idx[has_only_right_mask].flatten(),
                              all_depth_idx[has_left_and_right_mask].flatten()])

    col_idx = np.concatenate([all_depth_idx[has_only_left_mask_left].flatten(),
                              all_depth_idx[has_only_right_mask_right].flatten(),
                              all_depth_idx[has_left_and_right_mask_left].flatten(),
                              all_depth_idx[has_only_left_mask].flatten(),
                              all_depth_idx[has_only_right_mask].flatten(),
                              all_depth_idx[has_left_and_right_mask_right].flatten()])
    data_term = [-1] * np.sum(has_only_left_mask) + [1] * np.sum(has_only_right_mask) + [-0.5] * np.sum(has_left_and_right_mask) \
                + [1] * np.sum(has_only_left_mask_left) + [-1] * np.sum(has_only_right_mask_right) + [0.5] * np.sum(has_left_and_right_mask)
    D_horizontal = coo_matrix((data_term, (row_idx, col_idx)), shape=(num_depth, num_depth)) / step_size

    has_bottom_and_top_mask = np.logical_and.reduce((move_bottom_mask, move_top_mask, normal_mask))
    has_only_bottom_mask = np.logical_and(np.logical_xor(move_bottom_mask, normal_mask), normal_mask)
    has_only_top_mask = np.logical_and(np.logical_xor(move_top_mask, normal_mask), normal_mask)

    has_bottom_and_top_mask_bottom = np.pad(has_bottom_and_top_mask, ((1, 0), (0, 0)), "constant", constant_values=0)[:-1, :]
    has_bottom_and_top_mask_top = np.pad(has_bottom_and_top_mask, ((0, 1), (0, 0)), "constant", constant_values=0)[1:,:]

    has_only_bottom_mask_bottom = np.pad(has_only_bottom_mask, ((1, 0), (0, 0)), "constant", constant_values=0)[:-1, :]
    has_only_top_mask_top = np.pad(has_only_top_mask, ((0, 1), (0, 0)), "constant", constant_values=0)[1:, :]

    row_idx = np.concatenate([all_depth_idx[has_only_bottom_mask].flatten(),
                              all_depth_idx[has_only_top_mask].flatten(),
                              all_depth_idx[has_bottom_and_top_mask].flatten(),
                              all_depth_idx[has_only_bottom_mask].flatten(),
                              all_depth_idx[has_only_top_mask].flatten(),
                              all_depth_idx[has_bottom_and_top_mask].flatten()])

    col_idx = np.concatenate([all_depth_idx[has_only_bottom_mask_bottom].flatten(),
                              all_depth_idx[has_only_top_mask_top].flatten(),
                              all_depth_idx[has_bottom_and_top_mask_bottom].flatten(),
                              all_depth_idx[has_only_bottom_mask].flatten(),
                              all_depth_idx[has_only_top_mask].flatten(),
                              all_depth_idx[has_bottom_and_top_mask_top].flatten()])
    data_term = [-1] * np.sum(has_only_bottom_mask) + [1] * np.sum(has_only_top_mask) + [-0.5] * np.sum(
        has_bottom_and_top_mask) \
                + [1] * np.sum(has_only_bottom_mask_bottom) + [-1] * np.sum(has_only_top_mask_top) + [0.5] * np.sum(
        has_bottom_and_top_mask)
    D_vertical = coo_matrix((data_term, (row_idx, col_idx)), shape=(num_depth, num_depth)) / step_size

    return D_vertical, D_horizontal


class OrthographicDiscreteFunctional:
    # camera coordinates
    # x
    # |  z
    # | /
    # |/
    # o ---y
    # pixel coordinates
    # u
    # |
    # |
    # |
    # o ---v
    def __init__(self, data):
        self.method_name = "orthographic_discrete_functional"
        method_start = time.time()
        p = - data.n[data.mask, 0] / data.n[data.mask, 2]
        q = - data.n[data.mask, 1] / data.n[data.mask, 2]

        b = np.concatenate((p, q))
        Du, Dv= generate_dx_dy_wb(data.mask, data.step_size)
        A = vstack((Du, Dv))

        solver_start = time.time()
        z = lsqr(A, b, atol=1e-17, btol=1e-17)[0]
        solver_end = time.time()

        self.solver_runtime = solver_end - solver_start

        method_end = time.time()
        self.total_runtime = method_end - method_start
        self.residual = A @ z - b

        self.depth_map = np.ones_like(data.mask, dtype=np.float) * np.nan
        self.depth_map[data.mask] = z

        # create a mesh model from the depth map
        self.facets = construct_facets_from_depth_map_mask(data.mask)
        self.vertices = construct_vertices_from_depth_map_and_mask(data.mask, self.depth_map, data.step_size)
        self.surface = pv.PolyData(self.vertices, self.facets)

