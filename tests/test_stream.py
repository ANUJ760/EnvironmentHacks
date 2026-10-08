"""Unit tests for WasteStream modeling and composition validation."""

import unittest
from ecotwin.categories import WasteCategory
from ecotwin.exceptions import InvalidCompositionError, PhysicsViolationError
from ecotwin.stream import WasteStream
from ecotwin.units import Mass


class TestWasteStream(unittest.TestCase):
    def test_valid_stream_creation(self):
        stream = WasteStream.create(
            mass=Mass.tonnes(100.0),
            composition={
                WasteCategory.ORGANIC: 0.50,
                WasteCategory.RECYCLABLE: 0.30,
                WasteCategory.E_WASTE: 0.05,
                WasteCategory.RESIDUAL: 0.15,
            },
        )
        self.assertEqual(stream.mass.to_tonnes().value, 100.0)
        self.assertEqual(stream.get_category_mass(WasteCategory.ORGANIC).to_tonnes().value, 50.0)
        self.assertEqual(stream.get_category_mass(WasteCategory.RECYCLABLE).to_tonnes().value, 30.0)
        self.assertEqual(stream.get_category_mass(WasteCategory.E_WASTE).to_tonnes().value, 5.0)
        self.assertEqual(stream.get_category_mass(WasteCategory.RESIDUAL).to_tonnes().value, 15.0)

    def test_single_category_creation(self):
        stream = WasteStream.single_category(Mass.tonnes(50.0), WasteCategory.ORGANIC)
        self.assertEqual(stream.get_fraction(WasteCategory.ORGANIC), 1.0)
        self.assertEqual(stream.get_fraction(WasteCategory.RECYCLABLE), 0.0)
        self.assertEqual(stream.get_category_mass(WasteCategory.ORGANIC).to_tonnes().value, 50.0)

    def test_invalid_composition_sum_raises_error(self):
        # Sum is 0.8 instead of 1.0
        with self.assertRaises(InvalidCompositionError):
            WasteStream.create(
                mass=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 0.50,
                    WasteCategory.RECYCLABLE: 0.30,
                },
            )

        # Sum is 1.2 instead of 1.0
        with self.assertRaises(InvalidCompositionError):
            WasteStream.create(
                mass=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 0.60,
                    WasteCategory.RECYCLABLE: 0.60,
                },
            )

    def test_negative_composition_raises_error(self):
        with self.assertRaises(InvalidCompositionError):
            WasteStream.create(
                mass=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 1.20,
                    WasteCategory.RECYCLABLE: -0.20,
                },
            )

    def test_stream_splitting(self):
        stream = WasteStream.create(
            mass=Mass.tonnes(100.0),
            composition={
                WasteCategory.ORGANIC: 0.60,
                WasteCategory.RESIDUAL: 0.40,
            },
        )
        part = stream.split(0.3)
        self.assertEqual(part.mass.to_tonnes().value, 30.0)
        self.assertEqual(part.get_category_mass(WasteCategory.ORGANIC).to_tonnes().value, 18.0)
        self.assertEqual(part.get_category_mass(WasteCategory.RESIDUAL).to_tonnes().value, 12.0)

        with self.assertRaises(PhysicsViolationError):
            stream.split(1.5)

    def test_stream_combining(self):
        s1 = WasteStream.single_category(Mass.tonnes(60.0), WasteCategory.ORGANIC)
        s2 = WasteStream.single_category(Mass.tonnes(40.0), WasteCategory.RECYCLABLE)
        combined = s1.combine(s2)

        self.assertEqual(combined.mass.to_tonnes().value, 100.0)
        self.assertAlmostEqual(combined.get_fraction(WasteCategory.ORGANIC), 0.60)
        self.assertAlmostEqual(combined.get_fraction(WasteCategory.RECYCLABLE), 0.40)


if __name__ == "__main__":
    unittest.main()
