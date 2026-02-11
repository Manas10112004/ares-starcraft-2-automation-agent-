import sc2
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.buff_id import BuffId
from sc2.position import Point2

# --- CONFIGURATION ---
# Set this to TRUE to use Llama 3.2 (Research Mode)
# Set this to FALSE to use Hard-coded Logic (Production Mode)
USE_LIVE_BRAIN = True

# Import C++ Muscle (Always needed)
import ares_lib

# Import Brain only if needed
if USE_LIVE_BRAIN:
    try:
        import ares_brain

        print("SYSTEM: Llama 3.2 Brain Connected.")
    except ImportError:
        print("SYSTEM: Brain module missing. Defaulting to Logic.")
        USE_LIVE_BRAIN = False


class AresBot(BotAI):
    def __init__(self):
        super().__init__()
        self.current_strategy = "RUSH"
        self.last_brain_query = 0

    async def on_step(self, iteration: int):
        if iteration == 0:
            mode = "RESEARCH (Llama 3.2)" if USE_LIVE_BRAIN else "PRODUCTION (Logic)"
            await self.chat_send(f"Project Ares: {mode} Mode Online")

        # --- THE STRATEGY ENGINE ---
        new_strategy = self.current_strategy

        # OPTION A: Live Brain (Slow, Smart)
        if USE_LIVE_BRAIN:
            # Query every ~30 seconds (400 steps)
            if iteration - self.last_brain_query > 400:
                self.last_brain_query = iteration

                # Create Report
                my_army = self.units(UnitTypeId.ZERGLING).amount + self.units(UnitTypeId.ROACH).amount
                enemy_count = self.enemy_units.amount
                report = f"Time: {self.time / 60:.1f}m. Army: {my_army}. Enemy: {enemy_count}. Gas: {self.vespene}."

                # Add Context
                if self.enemy_units(UnitTypeId.SIEGETANKSIEGED).exists: report += " ENEMY HAS TANKS."
                if self.enemy_structures(UnitTypeId.BUNKER).exists: report += " ENEMY HAS BUNKERS."
                if self.enemy_units(UnitTypeId.BANSHEE).exists: report += " ENEMY HAS AIR UNITS."

                # Ask Llama (Blocking Call - might lag slightly)
                new_strategy = ares_brain.get_commander_orders(report)

        # OPTION B: Distilled Logic (Fast, Reliable)
        else:
            # Default to RUSH unless a rule stops us
            temp_strat = "RUSH"

            # Logic Gates (The "Distilled" Llama Lessons)
            if self.enemy_units(UnitTypeId.SIEGETANKSIEGED).exists or self.enemy_structures(UnitTypeId.BUNKER).exists:
                temp_strat = "MACRO"
            if self.enemy_units(UnitTypeId.BANSHEE).exists or self.enemy_units(UnitTypeId.VOIDRAY).exists:
                temp_strat = "COUNTER"
            if self.supply_used > 190:
                temp_strat = "RUSH"  # Kill command

            new_strategy = temp_strat

        # Apply Strategy Update
        if new_strategy != self.current_strategy:
            self.current_strategy = new_strategy
            await self.chat_send(f"Command Update: {new_strategy}")

        # --- THE BODY (Execution) ---
        await self.distribute_workers()

        # Macro / Expand Logic
        expand_threshold = 300 if self.current_strategy == "MACRO" else 500
        if self.minerals > expand_threshold and not self.already_pending(UnitTypeId.HATCHERY):
            await self.expand_now()

        # Worker Logic
        drone_limit = 65 if self.current_strategy == "MACRO" else 22
        if self.supply_workers < drone_limit:
            if self.structures(UnitTypeId.SPAWNINGPOOL).ready.amount > 0 or self.minerals > 250:
                if self.can_afford(UnitTypeId.DRONE):
                    self.train(UnitTypeId.DRONE)

        # Overlords
        if self.supply_left < 5 and not self.already_pending(UnitTypeId.OVERLORD):
            if self.can_afford(UnitTypeId.OVERLORD):
                self.train(UnitTypeId.OVERLORD)

        # Structures
        if self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
            if self.can_afford(UnitTypeId.SPAWNINGPOOL):
                await self.build(UnitTypeId.SPAWNINGPOOL, near=self.townhalls.first)

        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if self.structures(UnitTypeId.ROACHWARREN).amount + self.already_pending(UnitTypeId.ROACHWARREN) == 0:
                if self.can_afford(UnitTypeId.ROACHWARREN):
                    await self.build(UnitTypeId.ROACHWARREN, near=self.townhalls.first)

            # Gas (1 for Rush, 2 for Macro/Counter)
            gas_limit = 2 if self.current_strategy in ["MACRO", "COUNTER"] else 1
            if self.structures(UnitTypeId.EXTRACTOR).amount < gas_limit and not self.already_pending(
                    UnitTypeId.EXTRACTOR):
                if self.can_afford(UnitTypeId.EXTRACTOR):
                    drone = self.workers.random
                    targetg = self.vespene_geyser.closest_to(drone)
                    drone.build(UnitTypeId.EXTRACTOR, targetg)

        # Queens
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if self.units(UnitTypeId.QUEEN).amount < self.townhalls.amount and self.can_afford(UnitTypeId.QUEEN):
                self.train(UnitTypeId.QUEEN)

        for queen in self.units(UnitTypeId.QUEEN):
            if queen.energy >= 25:
                targets = self.townhalls.ready.filter(lambda h: not h.has_buff(BuffId.QUEENSPAWNLARVATIMER))
                if targets.exists:
                    queen(AbilityId.EFFECT_INJECTLARVA, targets.closest_to(queen))

        # Army Production
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            for larva in self.larva:
                if self.current_strategy in ["COUNTER", "MACRO"] and self.structures(
                        UnitTypeId.ROACHWARREN).ready and self.can_afford(UnitTypeId.ROACH):
                    larva.train(UnitTypeId.ROACH)
                elif self.can_afford(UnitTypeId.ZERGLING):
                    larva.train(UnitTypeId.ZERGLING)

        # --- THE MUSCLE (C++ Combat) ---
        should_attack = False
        army_count = self.units(UnitTypeId.ZERGLING).amount + self.units(UnitTypeId.ROACH).amount

        # Strategy Triggers
        if self.current_strategy == "RUSH" and army_count > 15:
            should_attack = True
        elif self.current_strategy == "COUNTER" and army_count > 30:
            should_attack = True
        elif self.current_strategy == "MACRO" and self.supply_used > 190:
            should_attack = True

        # Defense Trigger (Always active)
        if self.townhalls.exists and self.enemy_units.closer_than(20, self.townhalls.first).exists:
            should_attack = True

        if should_attack:
            # Prepare C++ Data
            my_units_data = []
            for u in self.units(UnitTypeId.ZERGLING) + self.units(UnitTypeId.ROACH):
                my_units_data.append(ares_lib.UnitData(u.tag, u.position.x, u.position.y, u.type_id.value, u.health))
            enemy_units_data = []
            for e in self.enemy_units:
                enemy_units_data.append(ares_lib.UnitData(e.tag, e.position.x, e.position.y, e.type_id.value, e.health))
            for s in self.enemy_structures:
                enemy_units_data.append(ares_lib.UnitData(s.tag, s.position.x, s.position.y, s.type_id.value, s.health))

            # Call C++
            assignments = ares_lib.get_focus_fire_targets(my_units_data, enemy_units_data)

            # Execute C++ Orders
            assigned_tags = set()
            my_unit_map = {u.tag: u for u in self.units}
            enemy_map = {e.tag: e for e in self.enemy_units + self.enemy_structures}

            for my_tag, target_tag in assignments:
                unit = my_unit_map.get(my_tag)
                target = enemy_map.get(target_tag)
                if unit and target:
                    unit.attack(target)
                    assigned_tags.add(my_tag)

            # Units without C++ orders move to target
            if self.enemy_structures.exists:
                move_target = self.enemy_structures.random.position
            else:
                move_target = self.enemy_start_locations[0]

            for u in self.units(UnitTypeId.ZERGLING) + self.units(UnitTypeId.ROACH):
                if u.tag not in assigned_tags:
                    u.attack(move_target)

        else:
            # Retreat
            if self.townhalls.exists:
                rally_point = self.townhalls.closest_to(self.game_info.map_center).position
                for u in self.units(UnitTypeId.ZERGLING) + self.units(UnitTypeId.ROACH):
                    u.move(rally_point)

        await self.manage_gas()

    async def manage_gas(self):
        for extractor in self.structures(UnitTypeId.EXTRACTOR).ready:
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                mineral_workers = self.workers.filter(
                    lambda w: w.is_gathering and w.order_target in self.mineral_field.tags)
                if mineral_workers.exists:
                    worker = mineral_workers.closest_to(extractor)
                    worker.gather(extractor)


# Run Game
run_game(
    sc2.maps.get("AbyssalReefLE"),
    [Bot(Race.Zerg, AresBot()), Computer(Race.Terran, Difficulty.VeryHard)],
    realtime=False  # Set to True to watch closely, False for speed
)