extends SceneTree

var failures: Array[String] = []

func _init() -> void:
    call_deferred("_run")

func _run() -> void:
    var packed := load("res://Main.tscn") as PackedScene
    _expect(packed != null, "Main.tscn loads")
    if packed != null:
        var main := packed.instantiate()
        _expect(main.get_script() != null and main.get_script().can_instantiate(), "Main script parses")
        _expect(main is Control, "Main root is a Control")
        _expect(main.name == "Main", "Main root is named Main")
        _expect(main.get_node_or_null("Background") is ColorRect, "Background exists")
        _expect(main.get_node_or_null("Margin/Content/Header") is PanelContainer, "Header exists")
        _expect(main.get_node_or_null("Margin/Content/MissionArea") is VBoxContainer, "MissionArea exists")
        _expect(main.get_node_or_null("Margin/Content/StationRow") is HBoxContainer, "StationRow exists")
        _expect(main.get_node_or_null("Margin/Content/MessageLog") is PanelContainer, "MessageLog exists")
        var switch_area := main.get_node_or_null("Margin/Content/SwitchArea") as Control
        _expect(switch_area != null, "SwitchArea exists")
        if switch_area != null:
            _expect(switch_area.custom_minimum_size.y >= 150.0, "SwitchArea reserves permanent height")
        _expect(main.get_node_or_null("Accessibility") is PanelContainer, "Accessibility panel exists")
        root.add_child(main)
        await process_frame
        var report_button := main.get_node("Margin/Content/SwitchArea/SwitchLayout/ActionRow").get_child(0) as Button
        _expect(report_button.text == "REPORT READY", "Scene 1 presents the readiness report")
        main.activate_switch_for_test()
        await process_frame
        _expect(report_button.disabled, "Direct switch input completes Scene 1 action")
        _expect("Readiness acknowledged" in main.get_node("Margin/Content/MessageLog/LogText").text, "Scene 1 records Command acknowledgement")
        main.free()
    _finish()

func _expect(condition: bool, description: String) -> void:
    if not condition:
        failures.append(description)
        printerr("FAIL: ", description)

func _finish() -> void:
    if failures.is_empty():
        print("PASS: baseline scene structure")
        quit(0)
    else:
        printerr("%d baseline assertions failed" % failures.size())
        quit(1)
