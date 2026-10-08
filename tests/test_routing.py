"""Unit tests for RoutingPlan and stream routing."""

import unittest
from ecotwin.categories import WasteCategory
from ecotwin.exceptions import InvalidRoutingError
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.routing import RouteSplit, RoutingPlan
from ecotwin.stream import WasteStream
from ecotwin.units import Mass


class TestRouting(unittest.TestCase):
    def setUp(self):
        self.fac1 = ProcessingFacility(
            name="Facility_A",
            capacity=Mass.tonnes(200.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.70,
                landfill_residue_rate=0.30,
            ),
        )
        self.fac2 = ProcessingFacility(
            name="Facility_B",
            capacity=Mass.tonnes(200.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.40,
                landfill_residue_rate=0.60,
            ),
        )
        self.facilities = {"Facility_A": self.fac1, "Facility_B": self.fac2}

    def test_direct_routing(self):
        plan = RoutingPlan.create_direct({
            WasteCategory.ORGANIC: "Facility_A",
            WasteCategory.RECYCLABLE: "Facility_B",
        })

        stream = WasteStream.create(
            mass=Mass.tonnes(100.0),
            composition={
                WasteCategory.ORGANIC: 0.60,
                WasteCategory.RECYCLABLE: 0.40,
            },
        )

        routed = plan.route_stream(stream, self.facilities)
        self.assertEqual(routed["Facility_A"].mass.to_tonnes().value, 60.0)
        self.assertEqual(routed["Facility_B"].mass.to_tonnes().value, 40.0)

    def test_split_routing(self):
        plan = RoutingPlan.create({
            WasteCategory.ORGANIC: [
                ("Facility_A", 0.70),
                ("Facility_B", 0.30),
            ],
            WasteCategory.RECYCLABLE: [
                ("Facility_B", 1.0),
            ],
        })

        stream = WasteStream.create(
            mass=Mass.tonnes(100.0),
            composition={
                WasteCategory.ORGANIC: 0.80, # 80 tonnes
                WasteCategory.RECYCLABLE: 0.20, # 20 tonnes
            },
        )

        routed = plan.route_stream(stream, self.facilities)
        # Facility A gets 80 * 0.7 = 56 tonnes
        self.assertAlmostEqual(routed["Facility_A"].mass.to_tonnes().value, 56.0)
        # Facility B gets 80 * 0.3 + 20 = 24 + 20 = 44 tonnes
        self.assertAlmostEqual(routed["Facility_B"].mass.to_tonnes().value, 44.0)

    def test_invalid_split_sum_raises_error(self):
        with self.assertRaises(InvalidRoutingError):
            RoutingPlan.create({
                WasteCategory.ORGANIC: [
                    ("Facility_A", 0.60),
                    ("Facility_B", 0.20),
                ] # sum = 0.80 != 1.0
            })

    def test_routing_to_missing_facility_raises_error(self):
        plan = RoutingPlan.create_direct({
            WasteCategory.ORGANIC: "Non_Existent_Facility",
        })
        stream = WasteStream.single_category(Mass.tonnes(50.0), WasteCategory.ORGANIC)
        with self.assertRaises(InvalidRoutingError):
            plan.route_stream(stream, self.facilities)

    def test_unrouted_category_present_in_stream_raises_error(self):
        plan = RoutingPlan.create_direct({
            WasteCategory.ORGANIC: "Facility_A",
        })
        # Stream has Recyclable which is not in plan
        stream = WasteStream.create(
            mass=Mass.tonnes(100.0),
            composition={
                WasteCategory.ORGANIC: 0.50,
                WasteCategory.RECYCLABLE: 0.50,
            },
        )
        with self.assertRaises(InvalidRoutingError):
            plan.route_stream(stream, self.facilities)


if __name__ == "__main__":
    unittest.main()
