import unittest

from omawpm.braille import BRAILLE_5X5, braille_graph, downsample_max, trim_leading_zeros


class DownsampleTests(unittest.TestCase):
    def test_pads_short_series_on_the_left(self):
        self.assertEqual(downsample_max([3, 4], 4), [0.0, 0.0, 3.0, 4.0])

    def test_keeps_peaks(self):
        self.assertEqual(downsample_max([1, 8, 2, 1], 2), [8.0, 2.0])

    def test_trim_leading_zeros(self):
        values, start = trim_leading_zeros([0, 0, 0, 5, 1], pad=1)
        self.assertEqual(start, 2)
        self.assertEqual(values, [0.0, 5.0, 1.0])


class GraphTests(unittest.TestCase):
    def test_table_is_btop_shape(self):
        self.assertEqual(BRAILLE_5X5[0][0], "⠀")
        self.assertEqual(BRAILLE_5X5[4][4], "⣿")
        self.assertEqual(BRAILLE_5X5[1][1], "⣀")

    def test_flat_zero_is_blank_cells(self):
        lines = braille_graph([0, 0, 0, 0], cols=2, rows=1, peak=10)
        self.assertEqual(lines, ["⠀⠀"])

    def test_full_scale_is_solid(self):
        lines = braille_graph([10, 10, 10, 10], cols=2, rows=1, peak=10)
        self.assertEqual(lines, ["⣿⣿"])

    def test_stacks_rows_from_the_bottom(self):
        lines = braille_graph([10, 10], cols=1, rows=2, peak=10)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1], "⣿")
        self.assertEqual(lines[0], "⣿")

    def test_column_count(self):
        lines = braille_graph(list(range(20)), cols=7, rows=3, peak=20)
        self.assertEqual(len(lines), 3)
        self.assertEqual(len(lines[0]), 7)


if __name__ == "__main__":
    unittest.main()
