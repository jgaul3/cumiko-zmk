from dataclasses import dataclass
import pcbnew
from math import sqrt


@dataclass
class Point:
    x: float
    y: float

    def to_wx_point_mm(self):
        return pcbnew.wxPointMM(self.x, self.y)

    def relational_point(self, x_offset, y_offset):
        return Point(self.x + x_offset, self.y + y_offset)

    def averaged_point(self, other_point, ratio=0.5):
        return Point(self.x * ratio + other_point.x * (1 - ratio), self.y * ratio + other_point.y * (1 - ratio))


ORIGIN = Point(50.1, 109.6)
TRIANGLE_SIDE_LENGTH = 15.25
TRIANGLE_HALF_SIDE_LENGTH = TRIANGLE_SIDE_LENGTH / 2
TRIANGLE_HEIGHT = TRIANGLE_HALF_SIDE_LENGTH * sqrt(3) 

TRIANGLE_THICKNESS = 1.1       
THIN_THICKNESS = 0.6
GOMA_RATIO = 0.15
SAKURA_RATIO = 0.70

FRONT = True


def add_track(start: Point, end: Point, thickness=TRIANGLE_THICKNESS):
    board = pcbnew.GetBoard()
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start.to_wx_point_mm())
    track.SetEnd(end.to_wx_point_mm())
    track.SetWidth(int(thickness * 1e6))
    track.SetLayer(pcbnew.F_Cu if FRONT else pcbnew.B_Cu)
    board.Add(track)

    mask_line = pcbnew.PCB_SHAPE()
    mask_line.SetStart(start.to_wx_point_mm())
    mask_line.SetEnd(end.to_wx_point_mm())
    mask_line.SetWidth(int(thickness * 1e6))
    mask_line.SetLayer(pcbnew.F_Mask if FRONT else pcbnew.B_Mask)
    board.Add(mask_line)


def add_zig_zag(start, width, down_first=True):
    offset = (0 if down_first else 1) * TRIANGLE_HEIGHT
    current_start = start.relational_point(0, offset)
    current_end = start.relational_point(TRIANGLE_HALF_SIDE_LENGTH, (1 if down_first else -1) * TRIANGLE_HEIGHT + offset)
    add_track(current_start, current_end)

    for i in range(width - 1):
        temp = current_start
        current_start = current_end
        current_end = temp.relational_point(TRIANGLE_SIDE_LENGTH, 0)
        add_track(current_start, current_end)


def add_grid(top_left_point, width, height):
    top_right_point = top_left_point.relational_point(width * TRIANGLE_SIDE_LENGTH / 2, 0)
    bottom_left_point = top_left_point.relational_point(0, height * TRIANGLE_HEIGHT)
    bottom_right_point = top_left_point.relational_point(width * TRIANGLE_SIDE_LENGTH / 2, height * TRIANGLE_HEIGHT)

    add_track(top_right_point, bottom_right_point)
    add_track(bottom_right_point, bottom_left_point)
    add_track(bottom_left_point, top_left_point)

    for i in range(height):
        left_point = top_left_point.relational_point(0, i * TRIANGLE_HEIGHT)
        right_point = top_right_point.relational_point(0, i * TRIANGLE_HEIGHT)
        add_track(left_point, right_point)
        add_zig_zag(left_point, width, not i % 2)

    decorate_grid(top_left_point, width, height)


def decorate_grid(top_left_point, width, height):
    for i in range(height):
        for j in range(width + 1):
            is_up = i % 2 != j % 2
            right_half = j != width
            left_half = j != 0

            top_point = top_left_point.relational_point(j * TRIANGLE_HALF_SIDE_LENGTH, (i + 1 if i % 2 != j % 2 else i) * TRIANGLE_HEIGHT)

            if FRONT:
                if i + j >= 2 * width / 3:
                    pattern_asanoha(top_point, is_up, right_half, left_half)
                else:
                    pattern_goma(top_point, is_up, right_half, left_half)
            else:
                if j - i < width / 3:
                    pattern_asanoha(top_point, is_up, right_half, left_half)
                else:
                    pattern_sakura(top_point, is_up, right_half, left_half)

            # if i % 3 == 0:
            #     pattern_asanoha(top_point, is_up, right_half, left_half)
            # elif i % 3 == 1:
            #     pattern_sakura(top_point, is_up, right_half, left_half)
            # else:
            #     pattern_goma(top_point, is_up, right_half, left_half)


def get_points(top_point, is_up):
    height_offset = (-1 if is_up else 1) * TRIANGLE_HEIGHT
    left_point = top_point.relational_point(-TRIANGLE_HALF_SIDE_LENGTH, height_offset)
    right_point = top_point.relational_point(TRIANGLE_HALF_SIDE_LENGTH, height_offset)
    centroid = Point((top_point.x + left_point.x + right_point.x) / 3, (top_point.y + left_point.y + right_point.y) / 3)
    return left_point, right_point, centroid


def draw_parallel_line(middle_point, ccw_point, cw_point, ratio=0.5):
    ccw_midpoint = middle_point.averaged_point(ccw_point, ratio)
    cw_midpoint = middle_point.averaged_point(cw_point, ratio)
    add_track(ccw_midpoint, cw_midpoint, THIN_THICKNESS)


def pattern_asanoha(top_point, is_up, right_half, left_half):
    left_point, right_point, centroid = get_points(top_point, is_up)

    if right_half and left_half:
        add_track(top_point, centroid, THIN_THICKNESS)
    if right_half:
        add_track(right_point, centroid, THIN_THICKNESS)
    if left_half:
        add_track(left_point, centroid, THIN_THICKNESS)


def pattern_sakura(top_point, is_up, right_half, left_half):
    left_point, right_point, centroid = get_points(top_point, is_up)

    def thick_sakura(middle_point, ccw_point, cw_point):
        for i in range(-5, 6):
            draw_parallel_line(middle_point, ccw_point, cw_point, SAKURA_RATIO + 0.01 * i)
        add_track(centroid, middle_point.averaged_point(centroid), THIN_THICKNESS)

    if right_half and left_half:
        corners = [top_point, left_point, right_point]
        for i in range(3):
            thick_sakura(corners[i], corners[(1 + i) % 3], corners[(2 + i) % 3])
    else:
        middle_point = left_point.averaged_point(right_point)
        if right_half:
            thick_sakura(top_point, right_point, middle_point)
            thick_sakura(right_point, top_point, left_point)
        if left_half:
            thick_sakura(top_point, middle_point, left_point)
            thick_sakura(left_point, right_point, top_point)



def pattern_goma(top_point, is_up, right_half, left_half):
    left_point, right_point, _ = get_points(top_point, is_up)
    if right_half and left_half:
        corners = [top_point, left_point, right_point]
        for i in range(3):
            draw_parallel_line(corners[i], corners[(1 + i) % 3], corners[(2 + i) % 3], GOMA_RATIO)
        
    else:
        middle_point = left_point.averaged_point(right_point)
        if right_half:
            draw_parallel_line(top_point, right_point, middle_point, GOMA_RATIO)  # Bottom line

            small_mid = right_point.averaged_point(top_point, GOMA_RATIO * 2)
            small_left = left_point.averaged_point(top_point, GOMA_RATIO * 2)
            draw_parallel_line(small_mid, small_left, top_point)  # Little top line

            mid_mid = right_point.averaged_point(left_point, GOMA_RATIO)
            mid_left = right_point.averaged_point(top_point, GOMA_RATIO)
            mid_ratio = GOMA_RATIO / (1 - GOMA_RATIO)
            draw_parallel_line(mid_mid, mid_left, right_point, mid_ratio)


        if left_half:
            draw_parallel_line(top_point, middle_point, left_point, GOMA_RATIO)

            small_mid = left_point.averaged_point(top_point, GOMA_RATIO * 2)
            small_right = right_point.averaged_point(top_point, GOMA_RATIO * 2)
            draw_parallel_line(small_mid, top_point, small_right)

            mid_mid = left_point.averaged_point(right_point, GOMA_RATIO)
            mid_right = left_point.averaged_point(top_point, GOMA_RATIO)
            mid_ratio = GOMA_RATIO / (1 - GOMA_RATIO)
            draw_parallel_line(mid_mid, left_point, mid_right, mid_ratio)


add_grid(ORIGIN, 15, 6)


pcbnew.Refresh()
