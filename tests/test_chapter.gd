extends SceneTree

var failures: Array[String] = []
var main: Control

func _init() -> void:
    call_deferred("_run")

func _run() -> void:
    main = (load("res://Main.tscn") as PackedScene).instantiate()
    root.add_child(main)
    await process_frame

    _expect(main.get("current_scene_index") == 0, "Chapter begins at Scene 1")
    await _activate("report_ready")
    await _activate("continue")
    _expect(main.get("current_scene_index") == 1, "Scene 1 advances to Scene 2")

    await _activate("continue")
    await _activate("continue")
    await _activate("continue")
    await _activate("actuate")
    _expect("Transition underway" in _log(), "Scene 2 completes a ready transition")
    await _activate("continue")
    _expect(main.get("current_scene_index") == 2, "Scene 2 advances to Scene 3")

    await _activate("actuate")
    _expect("Transition inhibited" in _log(), "Scene 3 early signal is inhibited")
    _expect("What did we expect?" in _log(), "Scene 3 applies debugging doctrine")
    await _activate("retry")
    await _activate("continue")
    await _activate("actuate")
    _expect("Sequence completed" in _log(), "Scene 3 retry can complete")
    await _activate("next_scene")
    _expect(main.get("current_scene_index") == 3, "Scene 3 advances to Scene 4")

    await _activate("hold")
    _expect("Hold acknowledged" in _log(), "Scene 4 accepts operator judgment")
    await _activate("continue")
    await _activate("actuate")
    _expect("Judgment confirmed" in _log(), "Scene 4 completes after interlock clears")
    await _activate("continue")
    _expect(main.get("current_scene_index") == 4, "Scene 4 advances to Scene 5")
    _expect("The syntax is new. The thought is not." in _log(), "Scene 5 reveals the procedure insight")
    _expect("initiate_transition()" in _log(), "Scene 5 reveals equivalent GDScript")
    main.get_node("Margin/Content/Accessibility/Controls/ScanToggle").button_pressed = true
    await _activate("complete")
    _expect(main.get_node("Margin/Content/SwitchArea/SwitchLayout/ActionRow").get_child(0).disabled, "Chapter completion disables further activation")
    _expect(not main.get_node("ScanController").enabled, "Chapter completion stops scanning")

    main.free()
    _finish()

func _activate(action: String) -> void:
    var found := false
    for button in main.get_node("Margin/Content/SwitchArea/SwitchLayout/ActionRow").get_children():
        if button.get_meta("action", "") == action:
            found = true
            button.pressed.emit()
            await process_frame
            break
    _expect(found, "Action '%s' is available" % action)

func _log() -> String:
    return main.get_node("Margin/Content/MessageLog/LogText").text

func _expect(condition: bool, description: String) -> void:
    if not condition:
        failures.append(description)
        printerr("FAIL: ", description)

func _finish() -> void:
    if failures.is_empty():
        print("PASS: complete five-scene chapter flow")
        quit(0)
    else:
        printerr("%d chapter assertions failed" % failures.size())
        quit(1)
