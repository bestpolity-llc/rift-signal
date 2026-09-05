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
        var accessibility := main.get_node_or_null("Margin/Content/Accessibility") as PanelContainer
        _expect(accessibility != null, "Accessibility panel participates in the main container layout")
        root.add_child(main)
        await process_frame
        if accessibility != null and switch_area != null:
            _expect(not accessibility.get_global_rect().intersects(switch_area.get_global_rect()), "Accessibility controls do not obscure SwitchArea")
        var title := main.get_node("Margin/Content/MissionArea/MissionTitle") as Label
        var original_title_size := title.get_theme_font_size("font_size")
        main.get_node("Margin/Content/Accessibility/Controls/TextSize").select(2)
        main._on_text_size_selected(2)
        _expect(title.get_theme_font_size("font_size") > original_title_size, "Text-size control scales explicit typography")
        var station_name := main.get_node("Margin/Content/StationRow").get_child(0).get_node("Layout/Text/StationName") as Label
        _expect(station_name.get_theme_font_size("font_size") > 15, "Text-size control scales reusable station typography")
        var vessel_status := main.get_node("Margin/Content/Header/HeaderRow/VesselStatus") as Label
        var instruction := main.get_node("Margin/Content/SwitchArea/SwitchLayout/Instruction") as Label
        _expect(vessel_status.get_theme_font_size("font_size") > 15, "Text-size control scales vessel status")
        _expect(instruction.get_theme_font_size("font_size") > 14, "Text-size control scales switch instruction")
        var report_button := main.get_node("Margin/Content/SwitchArea/SwitchLayout/ActionRow").get_child(0) as Button
        _expect(report_button.text == "REPORT READY", "Scene 1 presents the readiness report")
        var scan_toggle := main.get_node("Margin/Content/Accessibility/Controls/ScanToggle") as CheckButton
        scan_toggle.grab_focus()
        var control_event := InputEventKey.new()
        control_event.keycode = KEY_SPACE
        control_event.pressed = true
        _expect(not main.handle_unhandled_switch_key(control_event), "Focused accessibility controls retain Space input")
        _expect(report_button.text == "REPORT READY", "Accessibility key input does not trigger the mission action")
        scan_toggle.release_focus()
        var switch_event := InputEventKey.new()
        switch_event.keycode = KEY_ENTER
        switch_event.pressed = true
        _expect(main.handle_unhandled_switch_key(switch_event), "Unhandled Enter is accepted as switch input")
        await process_frame
        var next_button := main.get_node("Margin/Content/SwitchArea/SwitchLayout/ActionRow").get_child(0) as Button
        _expect(next_button.text == "ACCEPT ASSIGNMENT", "Enter activates the focused mission action")
        _expect("Readiness acknowledged" in main.get_node("Margin/Content/MessageLog/LogText").text, "Scene 1 records Command acknowledgement")
        main._advance_mission()
        var recreated_station_name := main.get_node("Margin/Content/StationRow").get_child(0).get_node("Layout/Text/StationName") as Label
        _expect(recreated_station_name.get_theme_font_size("font_size") > 15, "Text size persists when mission stations are recreated")
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
