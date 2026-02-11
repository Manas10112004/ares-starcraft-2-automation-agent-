#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>
#include <limits>

namespace py = pybind11;

struct UnitData {
    unsigned long long tag; // The unit's unique ID
    float x;
    float y;
    int type_id;            // To identify if it's a Tank, Marine, etc.
    float health;
};

// C++ Function: Assign the best target for every Zergling
// Returns: A list of pairs -> [ (ZerglingTag, TargetTag), ... ]
std::vector<std::pair<unsigned long long, unsigned long long>> get_focus_fire_targets(
    std::vector<UnitData> my_units,
    std::vector<UnitData> enemy_units
) {
    std::vector<std::pair<unsigned long long, unsigned long long>> assignments;

    // Loop through every single one of OUR units
    for (const auto& unit : my_units) {
        float best_score = -std::numeric_limits<float>::infinity();
        unsigned long long best_target_tag = 0;
        bool found_target = false;

        // Compare against every ENEMY unit
        for (const auto& enemy : enemy_units) {
            float dx = unit.x - enemy.x;
            float dy = unit.y - enemy.y;
            float dist_sq = dx*dx + dy*dy;
            float dist = std::sqrt(dist_sq);

            // OPTIMIZATION: Ignore enemies that are too far away (e.g. > 15 range)
            if (dist > 15.0f) continue;

            // --- SCORING SYSTEM ---
            float score = 0.0f;

            // Priority 1: High Threat Units (Tanks, Cyclones)
            // Note: These IDs are examples. Python will pass the raw int ID.
            if (enemy.type_id == 33 || enemy.type_id == 692) { // Siege Tank, Cyclone
                score += 100.0f;
            }
            // Priority 2: Standard Shooters (Marines, Marauders, Roaches)
            else if (enemy.type_id == 48 || enemy.type_id == 51) { // Marine, Marauder
                score += 50.0f;
            }
            // Priority 3: Workers (SCVs) - Good to kill if nearby
            else if (enemy.type_id == 45) { // SCV
                score += 20.0f;
            }
            // Priority 4: Buildings - Low priority
            else {
                score += 1.0f;
            }

            // Priority 5: Kill low HP units first (Reduce enemy DPS faster)
            if (enemy.health < 20.0f) score += 10.0f;

            // Distance Penalty: Subtract score based on distance
            // We want to kill high priority things, but not if they are miles away
            score -= (dist * 2.0f);

            // Is this the best target so far?
            if (score > best_score) {
                best_score = score;
                best_target_tag = enemy.tag;
                found_target = true;
            }
        }

        // If we found a valid target, add the assignment
        if (found_target) {
            assignments.push_back({unit.tag, best_target_tag});
        }
    }

    return assignments;
}

// Binding code
PYBIND11_MODULE(ares_lib, m) {
    py::class_<UnitData>(m, "UnitData")
        .def(py::init<unsigned long long, float, float, int, float>())
        .def_readwrite("tag", &UnitData::tag)
        .def_readwrite("x", &UnitData::x)
        .def_readwrite("y", &UnitData::y)
        .def_readwrite("type_id", &UnitData::type_id)
        .def_readwrite("health", &UnitData::health);

    m.def("get_focus_fire_targets", &get_focus_fire_targets, "Calculate best focus fire targets");
}