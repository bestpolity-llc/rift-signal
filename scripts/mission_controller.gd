extends Node

signal mission_changed(index: int, mission: Dictionary)
signal mission_step_changed(scene_index: int, step: int)
signal operator_signal(action: String, scene_index: int, step: int)
signal consequence(kind: String, detail: String)

var missions: Array[Dictionary] = []
var current_index := 0
var step := 0
var flags: Dictionary = {}

func configure(chapter_missions: Array[Dictionary]) -> void:
    missions = chapter_missions
    current_index = 0
    step = 0
    flags.clear()

func current_mission() -> Dictionary:
    if current_index < 0 or current_index >= missions.size():
        return {}
    return missions[current_index]

func advance_step() -> void:
    step += 1
    mission_step_changed.emit(current_index, step)

func advance_mission() -> bool:
    if current_index >= missions.size() - 1:
        return false
    current_index += 1
    step = 0
    flags.clear()
    mission_changed.emit(current_index, current_mission())
    return true

func record_operator_signal(action: String) -> void:
    operator_signal.emit(action, current_index, step)

func set_flag(key: String, value: Variant = true) -> void:
    flags[key] = value

func has_flag(key: String) -> bool:
    return bool(flags.get(key, false))
